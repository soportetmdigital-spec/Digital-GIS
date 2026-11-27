"""Cartografía del Catastro guardada en el servidor y parcelas catastrales para despliegues."""
import os
import shutil
from pathlib import Path
from unittest.mock import patch

from odoo.tests import HttpCase, TransactionCase, new_test_user, tagged

from ..models import catastro_tiles
from ..models.catastro_parcels import ADDRESSES_WFS_URL

DATA = Path(__file__).parent / "data"
PNG = b"\x89PNG\r\n\x1a\n" + b"tesela"


class TestCatastroTiles(TransactionCase):
    def setUp(self):
        super().setUp()
        catastro_tiles.clear_memory_cache()
        self.root = catastro_tiles.cache_root(self.env.cr.dbname)
        shutil.rmtree(self.root, ignore_errors=True)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(catastro_tiles.clear_memory_cache)

    def test_tile_is_downloaded_once_and_then_served_from_cache(self):
        calls = []

        def download(z, x, y):
            calls.append((z, x, y))
            return PNG

        dbname = self.env.cr.dbname
        self.assertEqual(catastro_tiles.get_tile(dbname, 16, 32000, 25000, download=download), PNG)
        self.assertTrue(os.path.exists(catastro_tiles.tile_path(dbname, 16, 32000, 25000)))
        self.assertEqual(catastro_tiles.get_tile(dbname, 16, 32000, 25000, download=download), PNG)
        catastro_tiles.clear_memory_cache()
        self.assertEqual(catastro_tiles.get_tile(dbname, 16, 32000, 25000, download=download), PNG)
        self.assertEqual(len(calls), 1, "Las siguientes peticiones salen de memoria o de disco.")

    def test_expired_tile_is_served_when_catastro_does_not_answer(self):
        dbname = self.env.cr.dbname
        catastro_tiles.get_tile(dbname, 15, 1, 1, download=lambda *args: PNG)
        path = catastro_tiles.tile_path(dbname, 15, 1, 1)
        old = os.path.getmtime(path) - 40 * 86400
        os.utime(path, (old, old))
        catastro_tiles.clear_memory_cache()
        self.assertEqual(catastro_tiles.get_tile(dbname, 15, 1, 1, max_age_days=30, download=lambda *args: None), PNG)
        self.assertIsNone(catastro_tiles.get_tile(dbname, 15, 2, 2, download=lambda *args: None))

    def test_invalid_tiles_and_cache_management(self):
        tiles = self.env["fiber.gis.catastro.tiles"]
        self.assertIsNone(tiles.get_tile_png(3, 0, 0))
        self.assertIsNone(tiles.get_tile_png(16, 2 ** 16, 0))
        catastro_tiles.get_tile(self.env.cr.dbname, 16, 3, 3, download=lambda *args: PNG)
        self.assertIn("1 teselas", tiles.cache_summary())
        tiles.clear_cache()
        self.assertIn("0 teselas", tiles.cache_summary())

    def test_precache_covers_the_network_in_batches(self):
        self.env["fiber.gis.node"].create([
            {"name": "Norte", "code": "TEST-PRE-N", "latitude": 37.180, "longitude": -3.600},
            {"name": "Sur", "code": "TEST-PRE-S", "latitude": 37.175, "longitude": -3.595},
        ])
        tiles = self.env["fiber.gis.catastro.tiles"]
        total = tiles.start_precache()
        self.assertGreater(total, 0)
        downloaded = []
        with patch.object(catastro_tiles, "download_tile", side_effect=lambda z, x, y, timeout=20: downloaded.append(z) or PNG), \
                patch.object(type(self.env["ir.cron"]), "_commit_progress", return_value=1000):
            tiles._cron_precache()
        self.assertFalse(tiles._precache_state(), "La precarga termina y se borra su estado.")
        self.assertEqual(sorted(set(downloaded)), list(tiles.PRECACHE_ZOOMS))


@tagged("post_install", "-at_install")
class TestCatastroTileRoute(HttpCase):
    def test_route_serves_cached_png(self):
        self.authenticate("admin", "admin")
        with patch.object(catastro_tiles, "download_tile", return_value=PNG):
            response = self.url_open("/fiber_gis/catastro/17/64000/50000.png")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "image/png")
        self.assertIn("max-age=86400", response.headers["Cache-Control"])
        self.assertEqual(self.url_open("/fiber_gis/catastro/3/0/0.png").status_code, 404)
        shutil.rmtree(catastro_tiles.cache_root(self.env.cr.dbname), ignore_errors=True)


def fake_catastro(url):
    """Respuestas reales guardadas: edificios y direcciones de dos parcelas de Granada."""
    name = "catastro_addresses.xml" if url.startswith(ADDRESSES_WFS_URL) else "catastro_buildings.xml"
    return (DATA / name).read_bytes()


class TestParcels(TransactionCase):
    def _run_imports(self):
        with patch.object(type(self.env["ir.cron"]), "_commit_progress", return_value=1000):
            self.env["fiber.gis.parcel.import"]._cron_run_imports(fetcher=fake_catastro)

    def test_plan_imports_parcels_with_dwellings_and_people(self):
        node = self.env["fiber.gis.node"].create({
            "name": "CTO plan", "code": "TEST-PARCEL-N", "latitude": 37.1742, "longitude": -3.6018,
        })
        plan = self.env["fiber.gis.deployment.plan"].create({"name": "Plan parcelas"})
        node.deployment_plan_id = plan
        plan.action_import_parcels()
        job = plan.parcel_import_ids
        self.assertEqual(job.state, "pending")
        self.assertGreater(job.cells_total, 0)
        self._run_imports()
        self.assertEqual(job.state, "done")
        self.assertEqual(job.cells_done, job.cells_total)
        parcel = self.env["fiber.gis.parcel"].search([("name", "=", "6645204VG4164F")])
        self.assertEqual((parcel.address, parcel.postcode, parcel.dwellings, parcel.building_units),
                         ("CL MORAL MAGDALENA 2", "18002", 5, 7))
        self.assertEqual(parcel.current_use, "1_residential")
        self.assertAlmostEqual(parcel.estimated_people, 12.5)
        self.assertEqual(plan.parcel_count, 2)
        self.assertEqual(plan.dwellings_total, 6)
        self.assertAlmostEqual(plan.people_total, 15.0)

    def test_reimport_updates_instead_of_duplicating(self):
        imports = self.env["fiber.gis.parcel.import"]
        imports.schedule(-3.6025, 37.1735, -3.6010, 37.1750, "Zona")
        self._run_imports()
        imports.schedule(-3.6025, 37.1735, -3.6010, 37.1750, "Zona otra vez")
        self._run_imports()
        self.assertEqual(self.env["fiber.gis.parcel"].search_count([("name", "in", ["6645204VG4164F", "6746001VG4164F"])]), 2)

    def test_household_size_recomputes_people(self):
        self.env["fiber.gis.parcel.import"].schedule(-3.6025, 37.1735, -3.6010, 37.1750, "Zona")
        self._run_imports()
        manager = new_test_user(self.env, login="gis_parcel_manager", groups="base.group_user,fiber_gis.group_fiber_gis_manager")
        settings = self.env["fiber.gis.settings.wizard"].with_user(manager).create({"household_size": 3.0})
        settings.action_save_settings()
        parcel = self.env["fiber.gis.parcel"].search([("name", "=", "6645204VG4164F")])
        self.assertAlmostEqual(parcel.estimated_people, 15.0)

    def test_import_resumes_when_the_cron_runs_out_of_time(self):
        # Dos celdas; el cron solo tiene tiempo para una en cada llamada.
        job = self.env["fiber.gis.parcel.import"].schedule(-3.6040, 37.1735, -3.5990, 37.1750, "Dos celdas")
        self.assertEqual(job.cells_total, 2)
        with patch.object(type(self.env["ir.cron"]), "_commit_progress", return_value=0) as progress:
            self.env["fiber.gis.parcel.import"]._cron_run_imports(fetcher=fake_catastro)
            self.assertEqual((job.state, job.cells_done), ("running", 1))
            self.assertEqual(progress.call_args.kwargs["remaining"], 1, "Odoo sabe que queda una celda y vuelve a llamar.")
            self.env["fiber.gis.parcel.import"]._cron_run_imports(fetcher=fake_catastro)
        self.assertEqual((job.state, job.cells_done), ("done", 2))
        self.assertEqual(progress.call_args.kwargs["remaining"], 0)

    def test_catastro_errors_are_recorded_and_import_continues(self):
        job = self.env["fiber.gis.parcel.import"].schedule(-3.6025, 37.1735, -3.6010, 37.1750, "Sin respuesta")

        def failing(url):
            raise TimeoutError("sin respuesta")

        with patch.object(type(self.env["ir.cron"]), "_commit_progress", return_value=1000):
            self.env["fiber.gis.parcel.import"]._cron_run_imports(fetcher=failing)
        self.assertEqual(job.state, "error")
        self.assertIn("no ha respondido", job.message)
        self.assertEqual(job.cells_done, job.cells_total)
