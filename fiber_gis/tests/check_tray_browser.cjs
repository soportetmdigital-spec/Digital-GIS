/* Plantilla y eventos en OWL real de Odoo 19; servicios RPC simulados. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require("playwright");

async function main() {
    const root = path.resolve(__dirname, "..");
    const qa = path.resolve(process.argv[2] || "qa");
    const samples = JSON.parse(fs.readFileSync(path.join(qa, "tray_samples.json"), "utf8"));
    const css = fs.readFileSync(path.join(root, "static/src/scss/fiber_map.scss"), "utf8");
    const source = fs.readFileSync(path.join(root, "static/src/js/fiber_diagram_field.js"), "utf8")
        .replace(/^import .+;\r?$/gm, "").replace("export class FiberDiagramField", "class FiberDiagramField");
    const templates = fs.readFileSync(path.join(root, "static/src/xml/fiber_diagram_field.xml"), "utf8");
    const browser = await chromium.launch({ headless: true, channel: process.env.PLAYWRIGHT_CHANNEL || undefined });
    try {
        const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
        const errors = [];
        page.on("pageerror", (error) => errors.push(error.message));
        await page.setContent(`<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
            body { font: 14px Arial; color: #172b3a; margin: 0; padding: 20px; }
            * { box-sizing: border-box; } h2 { font-size: 18px; font-weight: 500; }
            button { font: inherit; } .fixture { min-width: 0; margin-bottom: 24px; }
            ${css}</style></head><body>
            <section class="fixture"><h2>Bandejas</h2><div id="node-form"></div></section>
            <section class="o_fiber_tray_wizard_form fixture"><h2>Asistente Bandejas</h2>${samples.context}</section>
            <section class="fixture"><h2>Splitter principal</h2><div id="splitter-form"></div></section>
            <div id="other-field"></div></body></html>`);
        await page.addScriptTag({ path: path.join(qa, "owl.js") });
        await page.evaluate(async ({ source, templates, samples }) => {
            const { Component, markup, onWillUnmount, useRef, useState } = owl;
            const useService = (name) => owl.useEnv().services[name];
            const registry = { category: () => ({ add: (_name, def) => { window.Field = def.component; } }) };
            const ConfirmationDialog = class {};
            const standardFieldProps = { id: { type: String, optional: true }, name: { type: String },
                readonly: { type: Boolean, optional: true }, record: { type: Object } };
            eval(source);
            Object.assign(window, { calls: [], actions: [], notifications: [], pendingDialogs: [], confirmations: [], saves: [], loads: [] });
            const services = {
                orm: { call: async (...args) => {
                    window.calls.push(args);
                    if (window.waitForRPC) { await new Promise((resolve) => { window.releaseRPC = resolve; }); }
                    const [model, method, values] = args;
                    if (method === "action_open_fiber") {
                        const key = window.trayActionVariant || `fiber-${values[1]}`;
                        return JSON.parse(JSON.stringify(samples.actions[key].action));
                    }
                    if (method === "action_manage_connection") {
                        return JSON.parse(JSON.stringify(samples.actions[`output-${values[0][0]}`].action));
                    }
                    return true;
                } },
                action: { doAction: async (action, options) => {
                    // Contrato del action_service de Odoo 19: no deriva views de view_mode.
                    action.views.map(([viewId, viewType]) => {
                        if (!Number.isInteger(viewId) || viewType !== "form") { throw new Error("Vista de formulario incorrecta"); }
                    });
                    if (action.type !== "ir.actions.act_window" || action.target !== "new" || !action.res_model) {
                        throw new Error("Accion modal incompleta");
                    }
                    window.actions.push(action); window.pendingDialogs.push(options.onClose);
                } },
                dialog: { add: (_component, props, options) => window.confirmations.push({ props, options }) },
                notification: { add: (...args) => window.notifications.push(args) },
            };
            window.closeDialogs = async () => { for (const callback of window.pendingDialogs.splice(0)) { await callback(); } };
            const record = (resModel, resId, name, value) => {
                const item = { resModel, resId, isNew: false, context: { lang: "es_ES" }, data: { [name]: value },
                    dirty: false, saveResult: true,
                    isDirty: async function () { return this.dirty; },
                    save: async function () { window.saves.push(this.resId); return this.saveResult; },
                    load: async function () { window.loads.push(this.resId); } };
                item.model = { root: item };
                return item;
            };
            window.nodeRecord = record("fiber.gis.node", 30, "tray_visual_html",
                `<section class="o_fiber_tray_card" data-tray-id="1">${samples.tray}</section>` +
                '<section class="o_fiber_tray_card" data-tray-id="2" style="min-height:50px">Bandeja 2</section>');
            window.splitterRecord = record("fiber.gis.splitter", 50, "diagram_html", samples.splitter);
            const mount = async (selector, record, name) => {
                const app = new owl.App(window.Field, { templates, env: { services }, dev: true, props: { name, record, readonly: true } });
                await app.mount(document.querySelector(selector)); return app;
            };
            window.nodeApp = await mount("#node-form", window.nodeRecord, "tray_visual_html");
            window.splitterApp = await mount("#splitter-form", window.splitterRecord, "diagram_html");
            await mount("#other-field", record("other.model", 30, "description", "<b>No permitido</b>"), "description");
            // Los ancestros no pueden bloquear los eventos locales del componente.
            document.querySelector("#node-form").addEventListener("dblclick", (event) => event.stopPropagation());
            document.querySelector("#splitter-form").addEventListener("click", (event) => event.stopPropagation());
        }, { source, templates, samples });
        const calls = () => page.evaluate(() => window.calls);
        const close = () => page.evaluate(() => window.closeDialogs());
        const lastCall = async (model, method, args) => {
            await page.waitForFunction(() => window.calls.length > 0);
            assert.deepEqual((await calls()).at(-1), [model, method, args, { context: { lang: "es_ES" } }]);
        };
        const input = page.locator("#node-form [data-fiber-id='11'] b");
        const output = page.locator("#node-form [data-fiber-id='12'] i");
        await input.click();
        assert.equal((await calls()).length, 0, "Un clic en bandeja no abre");
        await input.dblclick();
        await lastCall("fiber.gis.tray.line", "action_open_fiber", [[41], 11]);
        await input.dblclick();
        assert.equal((await calls()).length, 1, "No duplica el asistente abierto");
        await close();
        await output.dblclick();
        await lastCall("fiber.gis.tray.line", "action_open_fiber", [[41], 12]);
        await close();
        for (const variant of ["rest", "splitter", "connected-output"]) {
            await page.evaluate((variant) => { window.trayActionVariant = variant; }, variant);
            await input.dblclick();
            const action = await page.evaluate(() => window.actions.at(-1));
            assert.equal(action.res_model, variant === "rest" ? "fiber.gis.cable.tray.wizard" : "fiber.gis.splitter");
            assert.deepEqual(action.views, [[variant === "rest" ? 101 : 102, "form"]]);
            await close();
        }
        await page.evaluate(() => { window.trayActionVariant = null; });
        for (const key of ["Enter", "Space"]) {
            await page.locator("#node-form article").focus();
            await page.keyboard.press(key);
            await lastCall("fiber.gis.tray.line", "action_open_fiber", [[41], 0]);
            await close();
        }
        await page.locator("[data-output-id='62']").click();
        await lastCall("fiber.gis.splitter.output", "action_manage_connection", [[62]]);
        await close();
        assert.deepEqual(await page.evaluate(() => window.saves), [], "No guarda formularios sin cambios");
        await page.evaluate(() => { window.splitterRecord.saveResult = false; });
        await page.locator("[data-output-id='61']").click();
        await lastCall("fiber.gis.splitter.output", "action_manage_connection", [[61]]);
        await close();
        const beforeDirty = (await calls()).length;
        await page.evaluate(() => { window.splitterRecord.dirty = true; });
        await page.locator("[data-output-id='63']").click();
        assert.equal((await calls()).length, beforeDirty, "Cambios invalidos bloquean la apertura");
        await page.evaluate(() => { window.splitterRecord.saveResult = true; });
        await page.locator("[data-output-id='63']").click();
        await lastCall("fiber.gis.splitter.output", "action_manage_connection", [[63]]);
        await close();
        await page.evaluate(() => { window.splitterRecord.dirty = false; });
        const beforeDelete = (await calls()).length;
        await page.locator("#node-form .o_fiber_tray_delete").click();
        assert.equal((await calls()).length, beforeDelete, "Borrar requiere confirmacion");
        await page.evaluate(() => window.confirmations.shift().options.onClose());
        assert.equal((await calls()).length, beforeDelete, "Cancelar no borra");
        await page.locator("#node-form .o_fiber_tray_delete").click();
        await page.evaluate(async () => {
            const confirmation = window.confirmations.shift();
            await confirmation.props.confirm(); confirmation.options.onClose();
        });
        await lastCall("fiber.gis.tray.line", "action_delete_visual_line", [41]);
        await page.evaluate(() => {
            const line = document.querySelector("#node-form article");
            const tray = document.querySelector("#node-form [data-tray-id='2']");
            const dataTransfer = new DataTransfer();
            for (const [element, type] of [[line, "dragstart"], [tray, "dragover"], [tray, "drop"], [line, "dragend"]]) {
                element.dispatchEvent(new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer }));
            }
        });
        await lastCall("fiber.gis.tray.line", "action_move_to_tray", [41, 2]);
        const afterDrop = (await calls()).length;
        await input.dispatchEvent("dblclick");
        assert.equal((await calls()).length, afterDrop, "Arrastrar no abre el asistente");
        assert.equal(await page.locator("#other-field").innerText(), "", "No renderiza HTML ajeno");
        assert.ok(await page.evaluate(() => window.loads.includes(30) && window.loads.includes(50)));
        for (const width of [1440, 768, 390]) {
            await page.setViewportSize({ width, height: 1000 });
            await page.locator("#node-form").evaluate((element, width) => { element.style.display = width < 768 ? "none" : "block"; }, width);
            const boxes = await page.locator(".o_fiber_splitter_output").evaluateAll((elements) =>
                elements.map((element) => ({ width: element.getBoundingClientRect().width, overflow: element.scrollWidth > element.clientWidth + 1 })));
            assert.ok(boxes.every((item) => item.width > 200 && !item.overflow), `Salidas legibles a ${width}px`);
            if (width === 390) { assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false); }
            await page.screenshot({ path: path.join(qa, `diagrams-${width}.png`), fullPage: true });
        }
        const actionsBeforeUnmount = await page.evaluate(() => window.actions.length);
        await page.evaluate(() => { window.waitForRPC = true; });
        await page.locator("[data-output-id='64']").click();
        await page.waitForFunction(() => window.releaseRPC);
        await page.evaluate(async () => {
            window.splitterApp.destroy(); window.releaseRPC();
            await new Promise((resolve) => setTimeout(resolve, 50));
        });
        assert.equal(await page.evaluate(() => window.actions.length), actionsBeforeUnmount, "No abre tras desmontar");
        assert.deepEqual(await page.evaluate(() => window.notifications), []);
        assert.deepEqual(errors, []);
        console.log("OK: OWL real y acciones Python reales con views; doble clic, salidas, guardado, borrado, arrastre y 3 anchuras.");
    } finally { await browser.close(); }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
