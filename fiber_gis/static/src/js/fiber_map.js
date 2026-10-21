/** @odoo-module **/

import {
    Component,
    onMounted,
    onPatched,
    onWillStart,
    onWillUnmount,
    useRef,
    useState,
} from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const EARTH_RADIUS = 6378137;
const DEFAULT_CENTER = { latitude: 37.183, longitude: -3.642 };
const DEFAULT_SCALE = 0.065;
const CATASTRO_WMS_URL = "https://ovc.catastro.meh.es/Cartografia/WMS/ServidorWMS.aspx";
const CATASTRO_START_ZOOM = 1.15;
const MAP_INTERACTION_IDLE_MS = 420;
const MAP_PAN_COMMIT_IDLE_MS = 90;
const CAMERA_SAVE_IDLE_MS = 180;
const CATASTRO_FRAME_PADDING = 0.35;
const CATASTRO_UPDATE_IDLE_MS = 120;
const CATASTRO_DETAIL_DELAY_MS = 850;
const CATASTRO_PREVIEW_QUALITY = 0.55;
const CATASTRO_REFRESH_SCALE_RATIO = 1.55;
const VIEWPORT_CULL_PADDING = 0.12;
const SEARCH_IDLE_MS = 1000;
const MAP_HISTORY_LIMIT = 30;
const CAMERA_STORAGE_KEY = "fiber_gis.map.camera";
const STREET_SEARCH_AREAS = [
    { key: "granada", name: "Granada capital", south: 37.145, west: -3.64, north: 37.215, east: -3.545 },
    { key: "santa_fe", name: "Santa Fe", south: 37.175, west: -3.745, north: 37.205, east: -3.68 },
];

export class FiberGisMap extends Component {
    static template = "fiber_gis.FiberGisMap";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.svg = useRef("svg");
        this.mapScene = useRef("mapScene");
        this.zoomIndicator = useRef("zoomIndicator");
        this.tooltip = useRef("tooltip");
        this.catastroImage = useRef("catastroImage");
        this.actionParams = this.props?.action?.params || this.props?.params || {};
        this.state = useState({
            sites: [],
            nodes: [],
            cables: [],
            types: {},
            cableProfiles: [],
            selectedSiteId: null,
            selectedNodeId: null,
            selectedCableId: null,
            pendingNodePlacementId: Number(this.actionParams.place_node_id || 0),
            searchDraft: "",
            searchQuery: "",
            searchResolvedQuery: "",
            inventorySearchResults: [],
            streetSearchResults: [],
            streetSearchLoading: false,
            streetSearchArea: "",
            streetSearchError: "",
            filter: "all",
            scale: 1,
            baseScale: 1,
            offsetX: 0,
            offsetY: 0,
            viewWidth: 1000,
            viewHeight: 700,
            bounds: null,
            showSitesLayer: true,
            showNodesLayer: true,
            showCablesLayer: true,
            showCustomerNodesLayer: true,
            showDropCablesLayer: true,
            showTraceLayer: true,
            showExistingNetwork: false,
            catastroRevision: 0,
            hiddenNodeKinds: [],
            contextMenu: null,
            trace: null,
            plan: null,
            planNodeIds: [],
            planCableIds: [],
            cableDraftMode: false,
            cableDraftFromNodeId: null,
            cableDraftToNodeId: null,
            cableDraftViaPoints: [],
            cableDraftCursor: null,
            cableDraftFromBoca: null,
            cableDraftToBoca: null,
            cableDraftFromBocas: [],
            cableDraftToBocas: [],
            cableDraftRouteKind: "underground",
            cableDraftTypeId: false,
            cableDraftChainIds: [],
            cableDraftFinalProfileId: false,
            showCableDraftFinalize: false,
            cableDraftFinalizing: false,
            cableDraftSaving: false,
            undoCount: 0,
            redoCount: 0,
            historyBusy: false,
            loading: true,
            mapDetailZoom: 0.67,
        });
        this._undoStack = [];
        this._redoStack = [];

        onWillStart(async () => {
            await this.loadData();
        });

        onMounted(() => {
            this.updateViewportSize();
            if (this.state.trace) {
                this.fitToTrace();
            } else if (this.focusActionTarget()) {
                // The form button should always win over the previously saved map camera.
            } else if (this.state.plan) {
                this.fitToPlan();
            } else if (!this.restoreCamera()) {
                this.fitToNetwork();
            }
            this.preparePendingNodePlacement();
            this.updateCatastroFrame({ immediate: true, quality: CATASTRO_PREVIEW_QUALITY });
            this.scheduleCatastroFrameUpdate({
                delay: CATASTRO_DETAIL_DELAY_MS,
                force: true,
                quality: 1,
            });
        });

        onPatched(() => {
            if (this._clearSceneTransformAfterPatch) {
                this._clearSceneTransformAfterPatch = false;
                this.clearSceneTransform();
            }
            this.updateZoomIndicator();
        });

        onWillUnmount(() => {
            clearTimeout(this._wheelTimer);
            clearTimeout(this._interactionCommitTimer);
            clearTimeout(this._saveCameraTimer);
            clearTimeout(this._catastroFrameTimer);
            clearTimeout(this._searchTimer);
            clearTimeout(this._tooltipTimer);
            if (this._sceneAnimationFrame) {
                cancelAnimationFrame(this._sceneAnimationFrame);
            }
            if (this._dragAnimationFrame) {
                cancelAnimationFrame(this._dragAnimationFrame);
            }
            this._catastroFrameRequestId = (this._catastroFrameRequestId || 0) + 1;
            this._catastroPreloadImage = null;
            this._streetSearchRequestId = (this._streetSearchRequestId || 0) + 1;
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const deploymentPlanId = Number(this.actionParams.deployment_plan_id || 0);
            const planScope = deploymentPlanId
                ? await this.orm.call("fiber.gis.deployment.plan", "get_map_scope", [deploymentPlanId])
                : null;
            const loadOnlyPlan = planScope && !this.state.showExistingNetwork;
            const siteDomain = loadOnlyPlan
                ? [["id", "in", planScope.site_ids || []], ["active", "=", true]]
                : [["active", "=", true]];
            const nodeDomain = loadOnlyPlan
                ? [["id", "in", planScope.node_ids || []]]
                : [["active", "=", true]];
            const cableDomain = loadOnlyPlan
                ? [["id", "in", planScope.cable_ids || []]]
                : [["active", "=", true]];
            const [sites, nodes, cables, types, mapDetailZoom, cableProfiles] = await Promise.all([
                this.orm.searchRead(
                    "fiber.gis.site",
                    siteDomain,
                    ["name", "code", "map_icon", "color", "state", "street", "city", "latitude", "longitude", "node_count"]
                ),
                this.orm.searchRead(
                    "fiber.gis.node",
                    nodeDomain,
                    [
                        "name",
                        "code",
                        "node_kind",
                        "type_id",
                        "deployment_plan_id",
                        "map_icon",
                        "color",
                        "state",
                        "latitude",
                        "longitude",
                        "address",
                        "partner_id",
                        "site_id",
                        "parent_id",
                        "child_count",
                        "manhole_type",
                        "manhole_model_id",
                        "manhole_length_cm",
                        "manhole_width_cm",
                        "manhole_depth_cm",
                        "capacity_ports",
                        "cable_entry_count",
                        "dowisp_id",
                        "dowisp_zone",
                        "dowisp_deployment",
                        "illuminated",
                        "olt_port",
                        "uuii",
                    ]
                ),
                this.orm.searchRead(
                    "fiber.gis.cable",
                    cableDomain,
                    [
                        "name",
                        "code",
                        "profile_id",
                        "type_id",
                        "deployment_plan_id",
                        "color",
                        "route_kind",
                        "route_segment_kinds",
                        "state",
                        "fiber_count",
                        "total_fiber_count",
                        "tube_count",
                        "length_m",
                        "from_node_id",
                        "from_boca",
                        "to_node_id",
                        "to_boca",
                        "from_latitude",
                        "from_longitude",
                        "to_latitude",
                        "to_longitude",
                        "geometry_geojson",
                    ]
                ),
                this.orm.searchRead(
                    "fiber.gis.asset.type",
                    [["active", "=", true]],
                    ["name", "code", "category", "color", "sequence"]
                ),
                this.orm.call("fiber.gis.site", "get_map_detail_zoom", []),
                this.orm.searchRead(
                    "fiber.gis.cable.profile",
                    [["active", "=", true]],
                    ["name", "gis_type_id", "tube_count", "fiber_count", "total_fiber_count"]
                ),
            ]);
            this.state.mapDetailZoom = Number(mapDetailZoom) || 0.67;
            this.state.cableProfiles = cableProfiles;
            this.state.sites = sites;
            this._sitesById = new Map(sites.map((site) => [site.id, site]));
            this.state.nodes = nodes;
            this._nodesById = new Map(nodes.map((node) => [node.id, node]));
            this.state.cables = cables;
            this._cablesById = new Map(cables.map((cable) => [cable.id, cable]));
            this._cablePointCache = new Map();
            this.state.plan = planScope?.plan || null;
            this.state.planNodeIds = planScope?.node_ids || [];
            this.state.planCableIds = planScope?.cable_ids || [];
            this.state.types = Object.fromEntries(types.map((type) => [type.id, type]));
            if (!this.cableTypes.some((type) => type.id === Number(this.state.cableDraftTypeId))) {
                this.state.cableDraftTypeId = this.defaultCableTypeId();
            }
            await this.loadTraceOverlay();
        } catch (error) {
            this.notification.add("No se han podido cargar los datos del mapa. Actualiza el m\u00f3dulo y recarga la p\u00e1gina.", { type: "danger" });
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    async loadTraceOverlay() {
        const nodeId = this.actionParams.trace_node_id;
        const fiberId = this.actionParams.trace_fiber_id;
        if (!nodeId || !fiberId) {
            this.state.trace = null;
            return;
        }
        const trace = await this.orm.call("fiber.gis.trace.wizard", "get_trace_map_data", [nodeId, fiberId]);
        this.state.trace = trace;
        this.state.filter = "all";
    }

    get filteredNodes() {
        if (!this.state.showNodesLayer) {
            return [];
        }
        const hiddenKinds = new Set(this.state.hiddenNodeKinds || []);
        const isPendingNode = (node) => this.state.pendingNodePlacementId === node.id;
        const isVisibleKind = (node) => isPendingNode(node) || !hiddenKinds.has(node.node_kind || "other");
        const isVisibleLocation = (node) => this.hasCoordinates(node) || isPendingNode(node);
        const isVisibleCustomer = (node) => (
            isPendingNode(node) || this.state.showCustomerNodesLayer || !this.isCustomerNode(node)
        );
        const viewport = this.paddedViewportGeoBounds(VIEWPORT_CULL_PADDING);
        return this.state.nodes.filter((node) => (
            (this.state.filter === "all" || node.state === this.state.filter)
            && isVisibleLocation(node)
            && isVisibleKind(node)
            && isVisibleCustomer(node)
            && (isPendingNode(node) || this.recordInGeoBounds(node, viewport))
        ));
    }

    get filteredSites() {
        if (!this.state.showSitesLayer) {
            return [];
        }
        const viewport = this.paddedViewportGeoBounds(VIEWPORT_CULL_PADDING);
        return this.state.sites.filter((site) => (
            this.hasCoordinates(site)
            && (this.state.filter === "all" || site.state === this.state.filter)
            && this.recordInGeoBounds(site, viewport)
        ));
    }

    get sitesWithoutCoordinates() {
        return this.state.sites.filter((site) => !this.hasCoordinates(site)).length;
    }

    get filteredCables() {
        if (!this.state.showCablesLayer) {
            return [];
        }
        const viewport = this.paddedViewportGeoBounds(VIEWPORT_CULL_PADDING);
        return this.state.cables.filter((cable) => {
            const stateMatches = this.state.filter === "all" || cable.state === this.state.filter;
            const typeMatches = this.state.showDropCablesLayer || !this.isDropCable(cable);
            return stateMatches && typeMatches && this.cableIntersectsGeoBounds(cable, viewport);
        });
    }

    get customerNodeCount() {
        return this.state.nodes.filter(
            (node) => this.hasCoordinates(node) && this.isCustomerNode(node)
        ).length;
    }

    get dropCableCount() {
        return this.state.cables.filter((cable) => this.isDropCable(cable)).length;
    }

    get nodeKindFilterOptions() {
        const counts = new Map();
        for (const node of this.state.nodes) {
            if (!this.hasCoordinates(node)) {
                continue;
            }
            const kind = node.node_kind || "other";
            counts.set(kind, (counts.get(kind) || 0) + 1);
        }
        return [...counts.entries()]
            .map(([kind, count]) => ({
                kind,
                count,
                label: this.nodeKindLabel(kind),
                checked: !(this.state.hiddenNodeKinds || []).includes(kind),
            }))
            .sort((left, right) => left.label.localeCompare(right.label));
    }

    get visibleTraceCables() {
        return this.state.showTraceLayer ? this.traceCables : [];
    }

    get selectedNode() {
        return this._nodesById?.get(this.state.selectedNodeId)
            || this.state.nodes.find((node) => node.id === this.state.selectedNodeId);
    }

    get selectedSite() {
        return this._sitesById?.get(this.state.selectedSiteId)
            || this.state.sites.find((site) => site.id === this.state.selectedSiteId);
    }

    get selectedCable() {
        return this._cablesById?.get(this.state.selectedCableId)
            || this.state.cables.find((cable) => cable.id === this.state.selectedCableId);
    }

    get cableTypes() {
        return this.state.cableProfiles
            .map((profile) => ({
                ...profile,
                category: "cable",
                name: `${profile.name} - Tipo GIS: ${Array.isArray(profile.gis_type_id) ? profile.gis_type_id[1] : "Sin definir"}`,
            }))
            .sort((left, right) => left.name.localeCompare(right.name));
    }

    get searchResults() {
        const query = this.normalizeSearchText((this.state.searchQuery || "").trim());
        if (query.length < 2 || this.state.searchResolvedQuery !== query) {
            return [];
        }
        return [
            ...this.state.inventorySearchResults.slice(0, 12),
            ...this.state.streetSearchResults.slice(0, 8),
        ];
    }

    inventorySearchResults(query) {
        const results = [];
        for (const site of this.state.sites) {
            if (this.recordMatches(site, query, ["name", "code", "street", "city"])) {
                results.push({
                    key: `site-${site.id}`,
                    kind: "site",
                    label: site.name || site.code || "Sitio sin nombre",
                    detail: ["Sitio", site.code, site.city].filter(Boolean).join(" \u00b7 "),
                    record: site,
                });
            }
        }
        for (const node of this.state.nodes) {
            if (this.recordMatches(node, query, ["name", "code", "address", "dowisp_id", "dowisp_zone", "olt_port"])) {
                results.push({
                    key: `node-${node.id}`,
                    kind: "node",
                    label: node.name || node.code || `Elemento ${node.id}`,
                    detail: [this.nodeKindLabel(node.node_kind), node.code, node.address].filter(Boolean).join(" \u00b7 "),
                    record: node,
                });
            }
        }
        for (const cable of this.state.cables) {
            const endpointNames = [
                Array.isArray(cable.from_node_id) ? cable.from_node_id[1] : "",
                Array.isArray(cable.to_node_id) ? cable.to_node_id[1] : "",
            ].join(" ");
            if (this.recordMatches({ ...cable, endpointNames }, query, ["name", "code", "endpointNames"])) {
                results.push({
                    key: `cable-${cable.id}`,
                    kind: "cable",
                    label: cable.name || cable.code || `Cable ${cable.id}`,
                    detail: ["Cable", cable.code, endpointNames].filter(Boolean).join(" \u00b7 "),
                    record: cable,
                });
            }
        }
        return results;
    }

    searchStreetContext(rawQuery) {
        const value = String(rawQuery || "").trim();
        const explicitAreas = [
            {
                area: STREET_SEARCH_AREAS[1],
                patterns: [
                    /^\s*santa\s*f[e\u00e9]\s*:\s*/i,
                    /\s*,\s*santa\s*f[e\u00e9]\s*$/i,
                    /\s+en\s+santa\s*f[e\u00e9]\s*$/i,
                    /\s+santa\s*f[e\u00e9]\s*$/i,
                ],
            },
            {
                area: STREET_SEARCH_AREAS[0],
                patterns: [
                    /^\s*granada(?:\s+capital)?\s*:\s*/i,
                    /\s*,\s*granada(?:\s+capital)?\s*$/i,
                    /\s+en\s+granada(?:\s+capital)?\s*$/i,
                    /\s+granada(?:\s+capital)?\s*$/i,
                ],
            },
        ];
        for (const candidate of explicitAreas) {
            for (const pattern of candidate.patterns) {
                if (pattern.test(value)) {
                    return {
                        area: candidate.area,
                        areas: [candidate.area],
                        query: value.replace(pattern, "").trim(),
                    };
                }
            }
        }
        const center = this.screenPixelToGeo(
            this.state.viewWidth / 2,
            this.state.viewHeight / 2
        );
        return {
            area: null,
            areas: STREET_SEARCH_AREAS,
            query: value,
        };
    }

    nearestStreetSearchArea(point) {
        return STREET_SEARCH_AREAS.reduce((nearest, area) => {
            const latitude = Math.max(area.south, Math.min(point.latitude, area.north));
            const longitude = Math.max(area.west, Math.min(point.longitude, area.east));
            const distance = Math.hypot(point.latitude - latitude, point.longitude - longitude);
            return !nearest || distance < nearest.distance ? { area, distance } : nearest;
        }, null).area;
    }

    recordMatches(record, query, fields) {
        return fields.some((field) => this.normalizeSearchText(record[field] || "").includes(query));
    }

    normalizeSearchText(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase();
    }

    hasCoordinates(record) {
        return Boolean(record.latitude && record.longitude);
    }

    paddedViewportGeoBounds(paddingRatio = 0) {
        if (!this.state.bounds || !this.state.viewWidth || !this.state.viewHeight) {
            return null;
        }
        return this.paddedVisibleGeoBounds(paddingRatio);
    }

    recordInGeoBounds(record, bounds) {
        if (!bounds || !this.hasCoordinates(record)) {
            return true;
        }
        return record.latitude >= bounds.south
            && record.latitude <= bounds.north
            && record.longitude >= bounds.west
            && record.longitude <= bounds.east;
    }

    cableIntersectsGeoBounds(cable, bounds) {
        if (!bounds || this.state.selectedCableId === cable.id) {
            return true;
        }
        const points = this.cableGeoPoints(cable);
        if (!points.length) {
            return false;
        }
        const extent = this._cablePointCache?.get(cable.id)?.extent || this.geoPointsExtent(points);
        return extent.west <= bounds.east
            && extent.east >= bounds.west
            && extent.south <= bounds.north
            && extent.north >= bounds.south;
    }

    project(latitude, longitude) {
        const x = (longitude * Math.PI * EARTH_RADIUS) / 180;
        const clampedLat = Math.max(Math.min(latitude, 85.05112878), -85.05112878);
        const y = EARTH_RADIUS * Math.log(Math.tan(Math.PI / 4 + (clampedLat * Math.PI) / 360));
        return { x, y: -y };
    }

    unproject(x, y) {
        const longitude = (x * 180) / (Math.PI * EARTH_RADIUS);
        const latitude = (Math.atan(Math.exp((-y / EARTH_RADIUS))) * 360) / Math.PI - 90;
        return { latitude, longitude };
    }

    mapPoint(latitude, longitude) {
        const point = this.project(latitude, longitude);
        const bounds = this.state.bounds || { minX: point.x, minY: point.y };
        return {
            x: (point.x - bounds.minX) * this.state.scale + this.state.offsetX,
            y: (point.y - bounds.minY) * this.state.scale + this.state.offsetY,
        };
    }

    nodeMapPoint(node) {
        if (this.hasCoordinates(node)) {
            return this.mapPoint(node.latitude, node.longitude);
        }
        if (this.state.pendingNodePlacementId === node.id) {
            return {
                x: this.state.viewWidth / 2,
                y: this.state.viewHeight / 2,
            };
        }
        return this.mapPoint(DEFAULT_CENTER.latitude, DEFAULT_CENTER.longitude);
    }

    preparePendingNodePlacement() {
        const nodeId = this.state.pendingNodePlacementId;
        if (!nodeId) {
            return;
        }
        const node = this.state.nodes.find((item) => item.id === nodeId);
        if (!node || this.hasCoordinates(node)) {
            return;
        }
        this.state.showNodesLayer = true;
        this.state.selectedNodeId = node.id;
        this.state.selectedSiteId = null;
        this.state.selectedCableId = null;
        this.notification.add("El elemento no tiene coordenadas. Arrastralo en el mapa para colocarlo y se guardara al soltar.", { type: "warning" });
    }

    focusActionTarget() {
        return this.focusActionTargetNode() || this.focusActionTargetCable();
    }

    focusActionTargetNode() {
        const nodeId = Number(this.actionParams.target_node_id || 0);
        if (!nodeId) {
            return false;
        }
        if (!this.state.bounds) {
            this.fitToNetwork();
        }
        const node = this.state.nodes.find((item) => item.id === nodeId);
        if (!node) {
            return false;
        }
        this.state.showNodesLayer = true;
        if (this.isCustomerNode(node)) {
            this.state.showCustomerNodesLayer = true;
        }
        this.state.selectedSiteId = null;
        this.state.selectedNodeId = node.id;
        this.state.selectedCableId = null;
        if (this.hasCoordinates(node)) {
            const minScale = Math.max((this.state.baseScale || this.state.scale || 1) * 45, 0.22);
            this.centerOnGeo(node.latitude, node.longitude, minScale);
        } else {
            this.state.pendingNodePlacementId = node.id;
            this.notification.add("El elemento no tiene coordenadas. Arrastralo en el mapa para colocarlo.", { type: "warning" });
        }
        return true;
    }

    focusActionTargetCable() {
        const cableId = Number(this.actionParams.target_cable_id || 0);
        if (!cableId) {
            return false;
        }
        if (!this.state.bounds) {
            this.fitToNetwork();
        }
        const cable = this.state.cables.find((item) => item.id === cableId);
        if (!cable) {
            return false;
        }
        this.state.showCablesLayer = true;
        if (this.isDropCable(cable)) {
            this.state.showDropCablesLayer = true;
        }
        this.state.selectedSiteId = null;
        this.state.selectedNodeId = null;
        this.state.selectedCableId = cable.id;
        this.centerOnCable(cable);
        return true;
    }

    centerOnGeo(latitude, longitude, minScale = 0.22) {
        if (!this.state.bounds || !latitude || !longitude) {
            return;
        }
        this.updateViewportSize();
        const point = this.project(latitude, longitude);
        this.state.scale = Math.max(this.state.scale, minScale);
        this.state.offsetX = this.state.viewWidth / 2 - (point.x - this.state.bounds.minX) * this.state.scale;
        this.state.offsetY = this.state.viewHeight / 2 - (point.y - this.state.bounds.minY) * this.state.scale;
        this.closeContextMenu();
        this.saveCamera();
    }

    centerOnCable(cable) {
        const points = this.cableGeoPoints(cable).filter((point) => point[0] && point[1]);
        if (!points.length) {
            this.notification.add("El cable no tiene coordenadas para centrarlo.", { type: "warning" });
            return;
        }
        const latitude = points.reduce((total, point) => total + point[0], 0) / points.length;
        const longitude = points.reduce((total, point) => total + point[1], 0) / points.length;
        this.centerOnGeo(latitude, longitude);
    }

    fitToStreet(street) {
        if (!this.state.bounds) {
            this.fitToNetwork();
        }
        const points = [];
        if (street.bounds) {
            const { south, west, north, east } = street.bounds;
            points.push(
                this.project(south, west),
                this.project(south, east),
                this.project(north, west),
                this.project(north, east)
            );
        } else if (street.latitude && street.longitude) {
            points.push(this.project(street.latitude, street.longitude));
        }
        for (const way of street.ways || []) {
            for (const coord of way.p || []) {
                if (coord[0] && coord[1]) {
                    points.push(this.project(coord[0], coord[1]));
                }
            }
        }
        if (!points.length) {
            this.notification.add("La calle no tiene geometr\u00eda suficiente para centrarla.", { type: "warning" });
            return;
        }
        this.updateViewportSize();
        const minX = Math.min(...points.map((point) => point.x));
        const maxX = Math.max(...points.map((point) => point.x));
        const minY = Math.min(...points.map((point) => point.y));
        const maxY = Math.max(...points.map((point) => point.y));
        const width = Math.max(maxX - minX, points.length === 1 ? 220 : 40);
        const height = Math.max(maxY - minY, points.length === 1 ? 220 : 40);
        const paddingX = Math.min(180, Math.max(80, this.state.viewWidth * 0.16));
        const paddingY = Math.min(150, Math.max(70, this.state.viewHeight * 0.16));
        this.state.scale = Math.min(
            (this.state.viewWidth - paddingX * 2) / width,
            (this.state.viewHeight - paddingY * 2) / height
        );
        this.state.scale = Math.max(this.state.scale, (this.state.baseScale || this.state.scale || 1) * CATASTRO_START_ZOOM);
        this.state.offsetX = this.state.viewWidth / 2 - ((minX + maxX) / 2 - this.state.bounds.minX) * this.state.scale;
        this.state.offsetY = this.state.viewHeight / 2 - ((minY + maxY) / 2 - this.state.bounds.minY) * this.state.scale;
        this.state.selectedSiteId = null;
        this.state.selectedNodeId = null;
        this.state.selectedCableId = null;
        this.closeContextMenu();
        this.saveCamera();
    }

    screenToGeo(clientX, clientY) {
        const rect = this.svg.el.getBoundingClientRect();
        return this.screenPixelToGeo(clientX - rect.left, clientY - rect.top);
    }

    screenPixelToGeo(x, y) {
        const bounds = this.state.bounds;
        const camera = this._interactionCamera || this.state;
        const internalX = (x - camera.offsetX) / camera.scale + bounds.minX;
        const internalY = (y - camera.offsetY) / camera.scale + bounds.minY;
        return this.unproject(internalX, internalY);
    }

    screenToInternalPoint(x, y) {
        const bounds = this.state.bounds || { minX: 0, minY: 0 };
        const camera = this._interactionCamera || this.state;
        return {
            x: (x - camera.offsetX) / camera.scale + bounds.minX,
            y: (y - camera.offsetY) / camera.scale + bounds.minY,
        };
    }

    fitToNetwork() {
        this.updateViewportSize();
        const locatedRecords = [...this.state.sites, ...this.state.nodes].filter((record) => this.hasCoordinates(record));
        const points = locatedRecords.map((record) => this.project(record.latitude, record.longitude));
        if (!points.length) {
            const center = this.project(DEFAULT_CENTER.latitude, DEFAULT_CENTER.longitude);
            this.state.bounds = { minX: center.x, minY: center.y, maxX: center.x, maxY: center.y };
            this.state.scale = DEFAULT_SCALE;
            this.state.baseScale = this.state.scale || 1;
            this.state.offsetX = this.state.viewWidth / 2;
            this.state.offsetY = this.state.viewHeight / 2;
            this.saveCamera();
            return;
        }
        const minX = Math.min(...points.map((point) => point.x));
        const maxX = Math.max(...points.map((point) => point.x));
        const minY = Math.min(...points.map((point) => point.y));
        const maxY = Math.max(...points.map((point) => point.y));
        const width = Math.max(maxX - minX, 100);
        const height = Math.max(maxY - minY, 100);
        this.state.bounds = { minX, minY, maxX, maxY };
        this.state.scale = Math.min((this.state.viewWidth - 180) / width, (this.state.viewHeight - 160) / height);
        this.state.baseScale = this.state.scale || 1;
        this.state.offsetX = 90;
        this.state.offsetY = 80;
        this.saveCamera();
    }

    fitToTrace() {
        this.updateViewportSize();
        const points = [];
        for (const cable of this.traceCables) {
            for (const point of this.cableGeoPoints(cable)) {
                if (point[0] && point[1]) {
                    points.push(this.project(point[0], point[1]));
                }
            }
        }
        for (const node of this.traceNodes) {
            if (this.hasCoordinates(node)) {
                points.push(this.project(node.latitude, node.longitude));
            }
        }
        if (!points.length) {
            this.fitToNetwork();
            return;
        }
        const minX = Math.min(...points.map((point) => point.x));
        const maxX = Math.max(...points.map((point) => point.x));
        const minY = Math.min(...points.map((point) => point.y));
        const maxY = Math.max(...points.map((point) => point.y));
        const width = Math.max(maxX - minX, 100);
        const height = Math.max(maxY - minY, 100);
        this.state.bounds = { minX, minY, maxX, maxY };
        this.state.scale = Math.min((this.state.viewWidth - 220) / width, (this.state.viewHeight - 180) / height);
        this.state.baseScale = this.state.scale || 1;
        this.state.offsetX = 110;
        this.state.offsetY = 90;
        this.saveCamera();
    }

    fitToPlan() {
        this.updateViewportSize();
        const points = [];
        for (const cable of this.planCables) {
            for (const point of this.cableGeoPoints(cable)) {
                if (point[0] && point[1]) {
                    points.push(this.project(point[0], point[1]));
                }
            }
        }
        for (const node of this.planNodes) {
            if (this.hasCoordinates(node)) {
                points.push(this.project(node.latitude, node.longitude));
            }
        }
        if (!points.length) {
            this.fitToNetwork();
            return;
        }
        const minX = Math.min(...points.map((point) => point.x));
        const maxX = Math.max(...points.map((point) => point.x));
        const minY = Math.min(...points.map((point) => point.y));
        const maxY = Math.max(...points.map((point) => point.y));
        const width = Math.max(maxX - minX, 100);
        const height = Math.max(maxY - minY, 100);
        this.state.bounds = { minX, minY, maxX, maxY };
        this.state.scale = Math.min(
            (this.state.viewWidth - 220) / width,
            (this.state.viewHeight - 180) / height
        );
        this.state.baseScale = this.state.scale || 1;
        this.state.offsetX = 110;
        this.state.offsetY = 90;
        this.saveCamera();
    }

    get zoomLabel() {
        return this.formatZoomLabel(this.state.scale);
    }

    formatZoomLabel(scale) {
        const baseScale = this.state.baseScale || scale || 1;
        const level = Math.max(scale / baseScale, 0.01);
        return `Zoom x${level.toFixed(level >= 10 ? 0 : 2)}`;
    }

    get zoomFactor() {
        const baseScale = this.state.baseScale || this.state.scale || 1;
        return Math.max(this.state.scale / baseScale, 0.01);
    }

    get undoButtonTitle() {
        const action = this._undoStack?.[this._undoStack.length - 1];
        return action ? `Deshacer: ${action.label}` : "No hay cambios para deshacer";
    }

    get redoButtonTitle() {
        const action = this._redoStack?.[this._redoStack.length - 1];
        return action ? `Rehacer: ${action.label}` : "No hay cambios para rehacer";
    }

    get showDetailedNodeIcons() {
        return this.zoomFactor >= this.state.mapDetailZoom;
    }

    get showNodeLabels() {
        return this.zoomFactor >= this.state.mapDetailZoom;
    }

    get traceCables() {
        const ids = new Set(this.state.trace?.cable_ids || []);
        return this.state.cables.filter((cable) => ids.has(cable.id));
    }

    get traceNodes() {
        const ids = new Set(this.state.trace?.node_ids || []);
        return this.state.nodes.filter((node) => ids.has(node.id));
    }

    get planCables() {
        const ids = new Set(this.state.planCableIds || []);
        return this.state.cables.filter((cable) => ids.has(cable.id));
    }

    get planNodes() {
        const ids = new Set(this.state.planNodeIds || []);
        return this.state.nodes.filter((node) => ids.has(node.id));
    }

    get cableDraftFromNode() {
        return this._nodesById?.get(this.state.cableDraftFromNodeId)
            || this.state.nodes.find((node) => node.id === this.state.cableDraftFromNodeId);
    }

    get cableDraftFromLabel() {
        const node = this.cableDraftFromNode;
        return node ? node.code || node.name || `Elemento ${node.id}` : "";
    }

    get cableDraftToNode() {
        return this._nodesById?.get(this.state.cableDraftToNodeId)
            || this.state.nodes.find((node) => node.id === this.state.cableDraftToNodeId);
    }

    get cableDraftFromBocas() {
        return this.state.cableDraftFromBocas;
    }

    get cableDraftToBocas() {
        return this.state.cableDraftToBocas;
    }

    async availableCableBocas(node) {
        if (!node) {
            return [];
        }
        return this.orm.call("fiber.gis.cable", "get_available_bocas", [node.id]);
    }

    get cableDraftGeoPoints() {
        const node = this.cableDraftFromNode;
        if (!node || !this.hasCoordinates(node)) {
            return [];
        }
        const points = [
            [node.latitude, node.longitude],
            ...(this.state.cableDraftViaPoints || []),
        ];
        const cursor = this._draftPreviewCursor || this.state.cableDraftCursor;
        if (cursor) {
            const previous = points[points.length - 1];
            if (!previous || previous[0] !== cursor[0] || previous[1] !== cursor[1]) {
                points.push(cursor);
            }
        }
        return points;
    }

    get cableDraftPath() {
        const points = this.cableDraftGeoPoints.map((point) => this.mapPoint(point[0], point[1]));
        if (points.length < 2) {
            return "";
        }
        return points.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
    }

    get cableDraftControlPoints() {
        return (this.state.cableDraftViaPoints || []).map((point, index) => {
            const mapPoint = this.mapPoint(point[0], point[1]);
            return {
                key: `draft-${index}`,
                x: mapPoint.x,
                y: mapPoint.y,
            };
        });
    }

    clearTrace() {
        this.state.trace = null;
    }

    async printTracePdf() {
        if (!this.state.trace?.wizard_id) {
            this.notification.add("No hay trazado para imprimir.", { type: "warning" });
            return;
        }
        const reportAction = await this.orm.call("fiber.gis.trace.wizard", "action_print_trace_pdf", [this.state.trace.wizard_id]);
        await this.action.doAction(reportAction);
    }

    async printDeploymentPlanPdf() {
        if (!this.state.plan?.id) {
            this.notification.add("No hay un plan de despliegue abierto.", { type: "warning" });
            return;
        }
        const reportAction = await this.orm.call(
            "fiber.gis.deployment.plan",
            "action_print_plan_pdf",
            [this.state.plan.id]
        );
        await this.action.doAction(reportAction);
    }

    async openDeploymentPlan() {
        if (!this.state.plan?.id) {
            return;
        }
        await this.openForm("fiber.gis.deployment.plan", this.state.plan.id);
    }

    async refreshPlanMetrics() {
        if (!this.state.plan?.id) {
            return;
        }
        const planScope = await this.orm.call(
            "fiber.gis.deployment.plan",
            "get_map_scope",
            [this.state.plan.id]
        );
        this.state.plan = planScope.plan;
        this.state.planNodeIds = planScope.node_ids || [];
        this.state.planCableIds = planScope.cable_ids || [];
    }

    async toggleExistingNetwork() {
        if (!this.state.plan) {
            return;
        }
        this.state.showExistingNetwork = !this.state.showExistingNetwork;
        await this.loadData();
    }

    saveCamera() {
        if (!this.state.bounds) {
            return;
        }
        clearTimeout(this._saveCameraTimer);
        try {
            localStorage.setItem(
                CAMERA_STORAGE_KEY,
                JSON.stringify({
                    scale: this.state.scale,
                    baseScale: this.state.baseScale || this.state.scale || 1,
                    offsetX: this.state.offsetX,
                    offsetY: this.state.offsetY,
                    bounds: this.state.bounds,
                    savedAt: Date.now(),
                })
            );
        } catch {
            // El mapa sigue funcionando aunque el navegador bloquee localStorage.
        }
        this.scheduleCatastroFrameUpdate();
    }

    scheduleSaveCamera() {
        clearTimeout(this._saveCameraTimer);
        this._saveCameraTimer = setTimeout(() => this.saveCamera(), CAMERA_SAVE_IDLE_MS);
    }

    restoreCamera() {
        try {
            const raw = localStorage.getItem(CAMERA_STORAGE_KEY);
            if (!raw) {
                return false;
            }
            const camera = JSON.parse(raw);
            if (!camera?.bounds || !Number.isFinite(camera.scale)) {
                return false;
            }
            this.state.bounds = camera.bounds;
            this.state.scale = camera.scale;
            this.state.baseScale = camera.baseScale || camera.scale || 1;
            this.state.offsetX = Number.isFinite(camera.offsetX) ? camera.offsetX : 90;
            this.state.offsetY = Number.isFinite(camera.offsetY) ? camera.offsetY : 80;
            return true;
        } catch {
            return false;
        }
    }

    updateViewportSize() {
        if (!this.svg.el) {
            return;
        }
        const container = this.svg.el.getBoundingClientRect();
        this.state.viewWidth = Math.max(container.width, 320);
        this.state.viewHeight = Math.max(container.height, 320);
    }

    get isInteracting() {
        return Boolean(
            this._panning ||
            this._wheelZooming ||
            this._draggingSiteId ||
            this._draggingNodeId ||
            this._draggingCablePoint
        );
    }

    get showCatastro() {
        return Boolean(this.state.bounds);
    }

    get catastroWebMap() {
        if (!this.showCatastro) {
            return null;
        }
        const frame = this._catastroFrame || this.buildCatastroFrame();
        if (!frame) {
            return null;
        }
        const topLeft = this.mapPoint(frame.north, frame.west);
        const bottomRight = this.mapPoint(frame.south, frame.east);
        return {
            url: frame.url,
            x: topLeft.x,
            y: topLeft.y,
            width: bottomRight.x - topLeft.x,
            height: bottomRight.y - topLeft.y,
        };
    }

    scheduleCatastroFrameUpdate(options = {}) {
        clearTimeout(this._catastroFrameTimer);
        const delay = options.delay ?? CATASTRO_UPDATE_IDLE_MS;
        this._catastroFrameTimer = setTimeout(() => this.updateCatastroFrame(options), delay);
    }

    updateCatastroFrame(options = {}) {
        const currentFrame = this._catastroFrame;
        if (!options.force && currentFrame && !this.catastroFrameNeedsRefresh(currentFrame)) {
            return;
        }
        const frame = this.buildCatastroFrame(options);
        if (!frame) {
            return;
        }
        if (frame.url === currentFrame?.url) {
            return;
        }
        if (options.immediate || !currentFrame) {
            this.applyCatastroFrame(frame);
            return;
        }
        const requestId = (this._catastroFrameRequestId || 0) + 1;
        this._catastroFrameRequestId = requestId;
        const image = new Image();
        image.decoding = "async";
        this._catastroPreloadImage = image;
        image.onload = () => {
            if (this._catastroFrameRequestId === requestId) {
                this.applyCatastroFrame(frame);
                this._catastroPreloadImage = null;
            }
        };
        image.onerror = () => {
            if (this._catastroFrameRequestId === requestId) {
                this._catastroPreloadImage = null;
                this.notification.add(
                    "Catastro no ha respondido. Se mantiene el plano anterior.",
                    { type: "warning" }
                );
            }
        };
        image.src = frame.url;
    }

    applyCatastroFrame(frame) {
        this._catastroFrame = frame;
        const image = this.catastroImage.el;
        if (!image) {
            this.state.catastroRevision += 1;
            return;
        }
        const topLeft = this.mapPoint(frame.north, frame.west);
        const bottomRight = this.mapPoint(frame.south, frame.east);
        image.setAttribute("href", frame.url);
        image.setAttribute("x", topLeft.x);
        image.setAttribute("y", topLeft.y);
        image.setAttribute("width", bottomRight.x - topLeft.x);
        image.setAttribute("height", bottomRight.y - topLeft.y);
    }

    catastroFrameNeedsRefresh(frame) {
        if (!frame) {
            return true;
        }
        const viewport = this.visibleGeoBounds();
        const isOutsideFrame = (
            viewport.west < frame.west ||
            viewport.south < frame.south ||
            viewport.east > frame.east ||
            viewport.north > frame.north
        );
        if (isOutsideFrame || (frame.quality || 0) < 0.99) {
            return true;
        }
        const frameScale = frame.scale || this.state.scale || 1;
        const scaleRatio = Math.max(
            this.state.scale / frameScale,
            frameScale / this.state.scale
        );
        return scaleRatio >= CATASTRO_REFRESH_SCALE_RATIO;
    }

    buildCatastroFrame(options = {}) {
        if (!this.showCatastro || !this.state.viewWidth || !this.state.viewHeight) {
            return null;
        }
        const quality = Math.min(Math.max(Number(options.quality) || 1, 0.45), 1);
        const viewport = this.paddedVisibleGeoBounds(CATASTRO_FRAME_PADDING);
        const frameRatio = 1 + CATASTRO_FRAME_PADDING * 2;
        const pixelRatio = Math.min(Math.max(window.devicePixelRatio || 1, 1.25), 1.75);
        const width = Math.min(
            Math.max(Math.round(this.state.viewWidth * frameRatio * pixelRatio * quality), quality < 1 ? 800 : 1200),
            3200
        );
        const height = Math.min(
            Math.max(Math.round(this.state.viewHeight * frameRatio * pixelRatio * quality), quality < 1 ? 600 : 900),
            2100
        );
        const params = new URLSearchParams({
            SERVICE: "WMS",
            VERSION: "1.1.1",
            REQUEST: "GetMap",
            FORMAT: "image/png",
            TRANSPARENT: "FALSE",
            SRS: "EPSG:4326",
            LAYERS: "Catastro",
            STYLES: "",
            BBOX: `${viewport.west},${viewport.south},${viewport.east},${viewport.north}`,
            WIDTH: `${width}`,
            HEIGHT: `${height}`,
        });
        return {
            url: `${CATASTRO_WMS_URL}?${params.toString()}`,
            west: viewport.west,
            south: viewport.south,
            east: viewport.east,
            north: viewport.north,
            scale: this.state.scale,
            quality,
        };
    }

    visibleGeoBounds() {
        const topLeft = this.screenPixelToGeo(0, 0);
        const bottomRight = this.screenPixelToGeo(this.state.viewWidth, this.state.viewHeight);
        return {
            west: Math.min(topLeft.longitude, bottomRight.longitude),
            south: Math.min(topLeft.latitude, bottomRight.latitude),
            east: Math.max(topLeft.longitude, bottomRight.longitude),
            north: Math.max(topLeft.latitude, bottomRight.latitude),
        };
    }

    paddedVisibleGeoBounds(paddingRatio = 0.5) {
        const topLeft = this.screenPixelToGeo(-this.state.viewWidth * paddingRatio, -this.state.viewHeight * paddingRatio);
        const bottomRight = this.screenPixelToGeo(
            this.state.viewWidth * (1 + paddingRatio),
            this.state.viewHeight * (1 + paddingRatio)
        );
        return {
            west: Math.min(topLeft.longitude, bottomRight.longitude),
            south: Math.min(topLeft.latitude, bottomRight.latitude),
            east: Math.max(topLeft.longitude, bottomRight.longitude),
            north: Math.max(topLeft.latitude, bottomRight.latitude),
        };
    }

    cablePoints(cable) {
        return this.cableGeoPoints(cable).map((point) => this.mapPoint(point[0], point[1]));
    }

    cableGeoPoints(cable) {
        const start = this.cableEndpoint(cable, "from");
        const end = this.cableEndpoint(cable, "to");
        const cacheKey = [
            start[0],
            start[1],
            end[0],
            end[1],
            cable.geometry_geojson || "",
        ].join("|");
        const cached = this._cablePointCache?.get(cable.id);
        if (cached?.key === cacheKey) {
            return cached.points;
        }
        const manualPoints = this.geojsonLinePoints(cable.geometry_geojson);
        const middlePoints = manualPoints.length > 2 ? manualPoints.slice(1, -1) : [];
        const points = [start, ...middlePoints, end];
        const validPoints = points.filter((point) => point[0] && point[1]);
        this._cablePointCache?.set(cable.id, {
            key: cacheKey,
            points: validPoints,
            extent: this.geoPointsExtent(validPoints),
        });
        return validPoints;
    }

    geoPointsExtent(points) {
        // El rectángulo se calcula una vez por geometría y se reutiliza al mover o ampliar el mapa.
        if (!points.length) {
            return null;
        }
        const extent = { south: Infinity, west: Infinity, north: -Infinity, east: -Infinity };
        for (const [latitude, longitude] of points) {
            extent.south = Math.min(extent.south, latitude);
            extent.north = Math.max(extent.north, latitude);
            extent.west = Math.min(extent.west, longitude);
            extent.east = Math.max(extent.east, longitude);
        }
        return extent;
    }

    cableEndpoint(cable, side) {
        const relation = side === "from" ? cable.from_node_id : cable.to_node_id;
        const node = this.nodeFromRelation(relation);
        if (node && this.hasCoordinates(node)) {
            return [node.latitude, node.longitude];
        }
        return side === "from"
            ? [cable.from_latitude, cable.from_longitude]
            : [cable.to_latitude, cable.to_longitude];
    }

    nodeFromRelation(relation) {
        const nodeId = Array.isArray(relation) ? relation[0] : relation;
        return this._nodesById?.get(nodeId) || this.state.nodes.find((node) => node.id === nodeId);
    }

    cablePath(cable) {
        const points = this.cablePoints(cable);
        if (!points.length) {
            return "";
        }
        return points.map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`).join(" ");
    }

    cableSegments(cable) {
        const points = this.cablePoints(cable);
        if (points.length < 2) {
            return [];
        }
        return points.slice(0, -1).map((point, index) => ({
            key: `${cable.id}-${index}`,
            index,
            path: `M ${point.x} ${point.y} L ${points[index + 1].x} ${points[index + 1].y}`,
        }));
    }

    cableControlPoints(cable) {
        const points = this.cablePoints(cable);
        if (points.length <= 2) {
            return [];
        }
        return points.slice(1, -1).map((point, index) => ({
            key: `${cable.id}-${index + 1}`,
            index: index + 1,
            x: point.x,
            y: point.y,
        }));
    }

    cableGeometryValue(cable, points = this.cableGeoPoints(cable)) {
        return JSON.stringify({
            type: "LineString",
            coordinates: points.map((geoPoint) => [
                Number(geoPoint[1].toFixed(7)),
                Number(geoPoint[0].toFixed(7)),
            ]),
        });
    }

    geojsonLinePoints(value) {
        if (!value) {
            return [];
        }
        try {
            const geometry = JSON.parse(value);
            if (geometry.type !== "LineString") {
                return [];
            }
            return geometry.coordinates.map((coord) => [coord[1], coord[0]]);
        } catch {
            return [];
        }
    }

    nodeColor(node) {
        const type = Array.isArray(node.type_id) ? this.state.types[node.type_id[0]] : null;
        const fallback = {
            olt: "#2563eb",
            odf: "#7c3aed",
            closure: "#d97706",
            cto: "#e11d48",
            box: "#059669",
            splitter: "#0891b2",
            manhole: "#475569",
            pole: "#64748b",
            ont: "#16a34a",
        };
        return node.color || type?.color || fallback[node.node_kind] || "#334155";
    }

    siteColor(site) {
        if (site.color) {
            return site.color;
        }
        if (site.state === "active") {
            return "#16a34a";
        }
        if (site.state === "maintenance") {
            return "#f59e0b";
        }
        if (site.state === "retired") {
            return "#64748b";
        }
        return "#2563eb";
    }

    mapIconPath(icon, size = 10) {
        if (icon === "diamond") {
            return `M 0 ${-size} L ${size} 0 L 0 ${size} L ${-size} 0 Z`;
        }
        if (icon === "triangle") {
            return `M 0 ${-size - 1} L ${size + 1} ${size} L ${-size - 1} ${size} Z`;
        }
        if (icon === "star") {
            return "M 0 -12 L 3 -4 L 11 -4 L 5 1 L 7 10 L 0 5 L -7 10 L -5 1 L -11 -4 L -3 -4 Z";
        }
        if (icon === "network") {
            return "M -11 -11 H 11 V 11 H -11 Z M -7 -7 V 7 H 7 V -7 Z M -2 -2 H 2 V 2 H -2 Z";
        }
        if (icon === "olt") {
            return "M -11 -10 H 11 V 10 H -11 Z M -7 -6 H 7 V -3 H -7 Z M -7 -1 H 7 V 2 H -7 Z M -7 4 H 7 V 7 H -7 Z";
        }
        if (icon === "odf") {
            return "M -10 -10 H 10 V 10 H -10 Z M -6 -6 H -2 V -2 H -6 Z M 2 -6 H 6 V -2 H 2 Z M -6 2 H -2 V 6 H -6 Z M 2 2 H 6 V 6 H 2 Z";
        }
        if (icon === "fdh") {
            return "M -11 -12 H 11 V 12 H -11 Z M -6 -8 H 6 V -4 H -6 Z M -6 1 H 6 V 5 H -6 Z M -3 12 H 3 V 15 H -3 Z";
        }
        if (icon === "cto") {
            return "M 0 -12 L 11 -5 V 7 L 0 12 L -11 7 V -5 Z M -5 -4 H 5 V 4 H -5 Z";
        }
        if (icon === "terminal") {
            return "M -11 -8 H 11 V 8 H -11 Z M -6 -3 H 6 V 3 H -6 Z M -2 8 H 2 V 12 H -2 Z";
        }
        if (icon === "cabinet") {
            return "M -9 -12 H 9 V 12 H -9 Z M -5 -8 H 5 V -5 H -5 Z M -5 -2 H 5 V 1 H -5 Z M -5 4 H 5 V 8 H -5 Z";
        }
        if (icon === "closure") {
            return "M -12 -7 H 12 V 7 H -12 Z M -7 -3 H 7 V 3 H -7 Z M -14 -2 H -12 V 2 H -14 Z M 12 -2 H 14 V 2 H 12 Z";
        }
        if (icon === "dome_closure") {
            return "M -9 10 H 9 V -2 C 9 -8 5 -12 0 -12 C -5 -12 -9 -8 -9 -2 Z M -12 10 H 12 V 14 H -12 Z";
        }
        if (icon === "splice") {
            return "M -12 -3 H -4 L -1 -7 H 1 L 4 -3 H 12 V 3 H 4 L 1 7 H -1 L -4 3 H -12 Z";
        }
        if (icon === "manhole") {
            return "M 0 -11 C 7 -11 12 -6 12 0 C 12 6 7 11 0 11 C -7 11 -12 6 -12 0 C -12 -6 -7 -11 0 -11 Z M 0 -6 C -4 -6 -7 -3 -7 0 C -7 3 -4 6 0 6 C 4 6 7 3 7 0 C 7 -3 4 -6 0 -6 Z";
        }
        if (icon === "chamber") {
            return "M -12 -9 H 12 V 9 H -12 Z M -8 -5 H 8 V 5 H -8 Z M -5 -1 H 5 V 1 H -5 Z";
        }
        if (icon === "handhole") {
            return "M -12 -6 C -12 -11 12 -11 12 -6 V 6 C 12 11 -12 11 -12 6 Z M -7 -2 H 7 V 2 H -7 Z";
        }
        if (icon === "pole") {
            return "M -2 -12 H 2 V 12 H -2 Z M -9 -8 H 9 V -5 H -9 Z M -7 3 H 7 V 6 H -7 Z";
        }
        if (icon === "aerial_strand") {
            return "M -12 -4 C -6 -10 6 2 12 -4 V 1 C 6 7 -6 -5 -12 1 Z";
        }
        if (icon === "duct") {
            return "M -12 -6 H 12 V -1 H -12 Z M -12 3 H 12 V 8 H -12 Z";
        }
        if (icon === "splitter") {
            return "M -11 -3 H -2 V -8 H 2 V -3 H 11 V 3 H 2 V 8 H -2 V 3 H -11 Z";
        }
        if (icon === "rack") {
            return "M -11 -12 H 11 V 12 H -11 Z M -7 -8 H 7 V -5 H -7 Z M -7 -2 H 7 V 1 H -7 Z M -7 4 H 7 V 7 H -7 Z M -8 10 H -5 V 12 H -8 Z M 5 10 H 8 V 12 H 5 Z";
        }
        if (icon === "ont") {
            return "M -10 -7 H 10 V 7 H -10 Z M -6 -3 H 2 V 1 H -6 Z M 5 -2 H 8 V 2 H 5 Z M -4 7 H 4 V 11 H -4 Z";
        }
        if (icon === "router") {
            return "M -11 -6 H 11 V 7 H -11 Z M -6 -10 L -2 -6 M 6 -10 L 2 -6 M -5 2 H -2 M 2 2 H 5";
        }
        if (icon === "drop") {
            return "M -12 -8 H -2 V -4 H 2 V -8 H 12 V -2 H 3 V 8 H -3 V -2 H -12 Z";
        }
        if (icon === "building") {
            return "M -10 -12 H 4 V 12 H -10 Z M 4 -4 H 12 V 12 H 4 Z M -6 -8 H -2 V -4 H -6 Z M -6 1 H -2 V 5 H -6 Z";
        }
        if (icon === "customer") {
            return "M 0 -11 C 4 -11 7 -8 7 -4 C 7 0 4 3 0 3 C -4 3 -7 0 -7 -4 C -7 -8 -4 -11 0 -11 Z M -10 13 C -8 6 8 6 10 13 Z";
        }
        if (icon === "customer_terminal") {
            return "M -13 -8 H 13 V 8 H -13 Z M -9 -4 H 5 V 0 H -9 Z M 8 -3 H 11 V 3 H 8 Z";
        }
        if (icon === "tray") {
            return "M -12 -8 H 12 V 8 H -12 Z M -8 -4 H 8 V -1 H -8 Z M -8 2 H 8 V 5 H -8 Z";
        }
        return "";
    }

    mapIconKind(record, fallback) {
        return record.map_icon || fallback;
    }

    cableColor(cable) {
        const type = Array.isArray(cable.type_id) ? this.state.types[cable.type_id[0]] : null;
        if (cable.state === "fault") {
            return "#dc2626";
        }
        return cable.color || type?.color || "#0f766e";
    }

    cableTypeLabel(cable) {
        if (Array.isArray(cable?.profile_id)) {
            return cable.profile_id[1];
        }
        const typeId = Array.isArray(cable?.type_id) ? cable.type_id[0] : cable?.type_id;
        return this.state.types[typeId]?.name || (Array.isArray(cable?.type_id) ? cable.type_id[1] : "") || "Sin tipo";
    }

    cableTypeCode(cable) {
        const typeId = Array.isArray(cable?.type_id) ? cable.type_id[0] : cable?.type_id;
        return this.state.types[typeId]?.code || "";
    }

    isDropCable(cable) {
        return this.cableTypeCode(cable) === "CABLE_DROP";
    }

    isCustomerNode(node) {
        return Boolean(node?.partner_id)
            || node?.map_icon === "customer"
            || node?.map_icon === "customer_terminal";
    }

    defaultCableTypeId() {
        const preferred = this.cableTypes.find((type) => type.code === "CABLE_DISTRIBUTION");
        return preferred?.id || this.cableTypes[0]?.id || false;
    }

    cableClass(cable) {
        const classes = [`is-${cable.route_kind || "underground"}`];
        if (this.cableTypeCode(cable) === "CABLE_DROP") {
            classes.push("is-customer-drop");
        }
        if (this.state.selectedCableId === cable.id) {
            classes.push("is-selected");
        }
        return classes.join(" ");
    }

    cableSegmentClass(cable, segment) {
        const classes = [`is-${this.cableSegmentKind(cable, segment.index)}`];
        if (this.cableTypeCode(cable) === "CABLE_DROP") {
            classes.push("is-customer-drop");
        }
        if (this.state.selectedCableId === cable.id) {
            classes.push("is-selected");
        } else if (
            this.state.plan &&
            this.state.showExistingNetwork &&
            !(this.state.planCableIds || []).includes(cable.id)
        ) {
            classes.push("is-reference");
        }
        return classes.join(" ");
    }

    nodeGroupClass(node) {
        const classes = ["o_fiber_gis_node"];
        if (!this.showDetailedNodeIcons) {
            classes.push("is-overview");
        }
        if (this.state.cableDraftMode) {
            classes.push(
                node.id === this.state.cableDraftFromNodeId
                    ? "is-cable-draft-source"
                    : "is-cable-draft-target"
            );
        }
        if (
            this.state.plan &&
            this.state.showExistingNetwork &&
            this.state.selectedNodeId !== node.id &&
            !(this.state.planNodeIds || []).includes(node.id)
        ) {
            classes.push("is-reference");
        }
        return classes.join(" ");
    }

    cableSegmentBaseClass(cable, segment) {
        return `o_fiber_gis_cable_base ${this.cableSegmentClass(cable, segment)}`;
    }

    cableSegmentKind(cable, segmentIndex) {
        return this.cableSegmentKinds(cable)[segmentIndex] || cable.route_kind || "underground";
    }

    cableSegmentKinds(cable) {
        const segmentCount = Math.max(this.cableGeoPoints(cable).length - 1, 0);
        let kinds = [];
        if (cable.route_segment_kinds) {
            try {
                const parsed = JSON.parse(cable.route_segment_kinds);
                kinds = Array.isArray(parsed) ? parsed : [];
            } catch {
                kinds = [];
            }
        }
        const fallback = cable.route_kind || "underground";
        return Array.from({ length: segmentCount }, (_, index) => kinds[index] || fallback);
    }

    routeKindLabel(value) {
        const labels = {
            facade: "Fachada",
            aerial: "A\u00e9reo",
            underground: "Subterr\u00e1neo",
        };
        return labels[value] || value || "";
    }

    nodeKindLabel(value) {
        const labels = {
            site: "Sitio t\u00e9cnico",
            olt: "OLT",
            odf: "ODF",
            rack: "Rack",
            cabinet: "Armario",
            cto: "CTO",
            box: "Caja terminal",
            closure: "Caja de registro",
            splitter: "Splitter",
            manhole: "Arqueta",
            pole: "Poste",
            ont: "ONT/CPE",
            other: "Otro",
        };
        return labels[value] || value || "";
    }

    recordTitle(kind, record) {
        if (kind === "site") {
            return "Sitio";
        }
        if (kind === "cable") {
            return "Cable";
        }
        return this.nodeKindLabel(record.node_kind) || "Elemento";
    }

    manholeLocationLabel(value) {
        const labels = {
            sidewalk: "Acera",
            roadway: "Calzada",
            garden: "Jard\u00edn",
            building: "Interior de edificio",
            other: "Otra",
        };
        return labels[value] || value || "";
    }

    scheduleTooltip(kind, record, ev) {
        if (this._draggingSiteId || this._draggingNodeId || this._draggingCablePoint || this._panning) {
            return;
        }
        clearTimeout(this._tooltipTimer);
        const rect = this.svg.el.getBoundingClientRect();
        const x = ev.clientX - rect.left + 14;
        const y = ev.clientY - rect.top + 14;
        this._tooltipTimer = setTimeout(() => {
            const tooltip = this.tooltip.el;
            if (!tooltip) {
                return;
            }
            const title = tooltip.querySelector("[data-tooltip-title]");
            const lines = tooltip.querySelector("[data-tooltip-lines]");
            if (title) {
                title.textContent = `${this.recordTitle(kind, record)}: ${record.name || record.code}`;
            }
            if (lines) {
                lines.replaceChildren(...this.tooltipLines(kind, record).map((line) => {
                    const span = document.createElement("span");
                    span.textContent = line;
                    return span;
                }));
            }
            tooltip.style.left = `${x}px`;
            tooltip.style.top = `${y}px`;
            tooltip.style.display = "grid";
        }, 1000);
    }

    cancelTooltip() {
        clearTimeout(this._tooltipTimer);
        if (this.tooltip.el) {
            this.tooltip.el.style.display = "none";
        }
    }

    tooltipLines(kind, record) {
        if (kind === "site") {
            return [
                `Matricula: ${record.code || ""}`,
                `Estado: ${this.stateLabel(record.state)}`,
                `Ciudad: ${record.city || ""}`,
                `Elementos: ${record.node_count || 0}`,
            ];
        }
        if (kind === "node") {
            const lines = [
                `Matricula: ${record.code || ""}`,
                `Tipo: ${this.nodeKindLabel(record.node_kind)}`,
                `Estado: ${this.stateLabel(record.state)}`,
            ];
            if (record.node_kind === "manhole") {
                lines.push(`Arqueta: ${record.manhole_model_id?.[1] || "Sin tipo"}`);
                lines.push(`Ubicaci\u00f3n: ${this.manholeLocationLabel(record.manhole_type) || "Sin indicar"}`);
                lines.push(`Medidas: ${this.manholeDimensions(record)}`);
                lines.push(`Elementos interiores: ${record.child_count || 0}`);
            } else if (record.node_kind === "cto") {
                if (record.address) {
                    lines.push(`Direcci\u00f3n: ${record.address}`);
                }
                if (record.dowisp_id) {
                    lines.push(`ID Dowisp: ${record.dowisp_id}`);
                }
                if (record.dowisp_zone || record.dowisp_deployment) {
                    lines.push(`Zona/despliegue: ${record.dowisp_zone || ""} ${record.dowisp_deployment || ""}`.trim());
                }
                if (record.olt_port) {
                    lines.push(`Puerto OLT: ${record.olt_port}`);
                }
                lines.push(`Iluminada: ${record.illuminated ? "S\u00ed" : "No"}`);
            } else if (record.capacity_ports) {
                lines.push(`Puertos: ${record.capacity_ports}`);
            }
            return lines;
        }
        return [
            `Matricula: ${record.code || ""}`,
            `Tipo: ${this.cableTypeLabel(record)}`,
            `Estado: ${this.stateLabel(record.state)}`,
            `Fibras: ${record.total_fiber_count || record.fiber_count || 0}`,
            `Tubos: ${record.tube_count || 0}`,
            `Longitud: ${this.round(record.length_m)} m`,
        ];
    }

    manholeDimensions(node) {
        const length = this.round(node.manhole_length_cm);
        const width = this.round(node.manhole_width_cm);
        const depth = this.round(node.manhole_depth_cm);
        if (!length && !width && !depth) {
            return "Sin medidas";
        }
        return `${length || "-"} x ${width || "-"} x ${depth || "-"} cm`;
    }

    selectSite(site) {
        this.state.selectedSiteId = site.id;
        this.state.selectedNodeId = null;
        this.state.selectedCableId = null;
    }

    selectNode(node) {
        this.state.selectedSiteId = null;
        this.state.selectedNodeId = node.id;
        this.state.selectedCableId = null;
    }

    selectCable(cable) {
        this.state.selectedSiteId = null;
        this.state.selectedCableId = cable.id;
        this.state.selectedNodeId = null;
    }

    async focusSearchResult(result) {
        if (result.kind === "site") {
            this.selectSite(result.record);
            if (this.hasCoordinates(result.record)) {
                this.centerOnGeo(result.record.latitude, result.record.longitude);
            } else {
                this.notification.add("El sitio no tiene coordenadas.", { type: "warning" });
            }
        } else if (result.kind === "node") {
            this.state.showNodesLayer = true;
            if (this.isCustomerNode(result.record)) {
                this.state.showCustomerNodesLayer = true;
            }
            this.selectNode(result.record);
            if (this.hasCoordinates(result.record)) {
                this.centerOnGeo(result.record.latitude, result.record.longitude);
            } else {
                this.notification.add("El elemento no tiene coordenadas.", { type: "warning" });
            }
        } else if (result.kind === "cable") {
            this.state.showCablesLayer = true;
            if (this.isDropCable(result.record)) {
                this.state.showDropCablesLayer = true;
            }
            this.selectCable(result.record);
            this.centerOnCable(result.record);
        } else if (result.kind === "street") {
            try {
                const geometry = result.record.latitude && result.record.longitude
                    ? result.record
                    : await this.orm.call(
                        "fiber.gis.site", "locate_map_street",
                        [result.record.catastro_id, result.record.area_key]
                    );
                this.fitToStreet({ ...result.record, ...geometry });
            } catch {
                this.notification.add("No se ha podido situar la calle desde Catastro.", {
                    type: "warning",
                });
            }
        }
    }

    clearSearch() {
        clearTimeout(this._searchTimer);
        this._streetSearchRequestId = (this._streetSearchRequestId || 0) + 1;
        this.state.searchDraft = "";
        this.state.searchQuery = "";
        this.state.searchResolvedQuery = "";
        this.state.inventorySearchResults = [];
        this.state.streetSearchResults = [];
        this.state.streetSearchLoading = false;
        this.state.streetSearchArea = "";
        this.state.streetSearchError = "";
    }

    onSearchInput(ev) {
        const value = ev.target.value;
        this.state.searchDraft = value;
        clearTimeout(this._searchTimer);
        this._streetSearchRequestId = (this._streetSearchRequestId || 0) + 1;
        this.state.searchQuery = "";
        this.state.searchResolvedQuery = "";
        this.state.inventorySearchResults = [];
        this.state.streetSearchResults = [];
        this.state.streetSearchLoading = false;
        this.state.streetSearchError = "";
        this._searchTimer = setTimeout(() => {
            this.runSearch(value);
        }, SEARCH_IDLE_MS);
    }

    async runSearch(rawQuery) {
        const normalizedQuery = this.normalizeSearchText(String(rawQuery || "").trim());
        this.state.searchQuery = rawQuery;
        this.state.searchResolvedQuery = normalizedQuery;
        this.state.inventorySearchResults = [];
        this.state.streetSearchResults = [];
        this.state.streetSearchArea = "";
        this.state.streetSearchError = "";
        if (normalizedQuery.length < 2) {
            return;
        }
        const context = this.searchStreetContext(rawQuery);
        const streetQuery = context.query.trim();
        const inventoryResults = this.inventorySearchResults(
            this.normalizeSearchText(streetQuery)
        );
        this.state.inventorySearchResults = inventoryResults;
        this.state.streetSearchArea = context.areas.map((area) => area.name).join(" y ");
        if (this.normalizeSearchText(streetQuery).length < 2) {
            return;
        }
        const requestId = (this._streetSearchRequestId || 0) + 1;
        this._streetSearchRequestId = requestId;
        this.state.streetSearchLoading = true;
        try {
            const responses = await Promise.all(context.areas.map((area) => (
                this.orm.call(
                    "fiber.gis.site",
                    "search_map_streets",
                    [streetQuery, area.key]
                )
            )));
            if (this._streetSearchRequestId !== requestId) {
                return;
            }
            const streets = responses.flatMap((items) => items || []);
            this.state.streetSearchResults = streets.map((street, index) => ({
                key: `street-${street.area_key}-${street.catastro_id || index}`,
                kind: "street",
                label: street.name,
                detail: `Catastro \u00b7 ${street.municipality} \u00b7 ${street.display_name}`,
                record: street,
            }));
        } catch {
            if (this._streetSearchRequestId === requestId) {
                this.state.streetSearchError = "No se ha podido consultar Catastro.";
            }
        } finally {
            if (this._streetSearchRequestId === requestId) {
                this.state.streetSearchLoading = false;
            }
        }
    }

    toggleMapLayer(layer) {
        const fieldName = {
            sites: "showSitesLayer",
            nodes: "showNodesLayer",
            cables: "showCablesLayer",
            customers: "showCustomerNodesLayer",
            dropCables: "showDropCablesLayer",
            trace: "showTraceLayer",
        }[layer];
        if (fieldName) {
            this.state[fieldName] = !this.state[fieldName];
        }
    }

    toggleNodeKind(kind) {
        const hiddenKinds = new Set(this.state.hiddenNodeKinds || []);
        if (hiddenKinds.has(kind)) {
            hiddenKinds.delete(kind);
        } else {
            hiddenKinds.add(kind);
        }
        this.state.hiddenNodeKinds = [...hiddenKinds];
    }

    async openSelected() {
        const site = this.selectedSite;
        const node = this.selectedNode;
        const cable = this.selectedCable;
        if (site) {
            await this.openForm("fiber.gis.site", site.id);
        } else if (node) {
            await this.openForm("fiber.gis.node", node.id);
        } else if (cable) {
            await this.openForm("fiber.gis.cable", cable.id);
        }
    }

    async openForm(model, resId = false, context = {}) {
        this.saveCamera();
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
            context,
        });
    }

    async createNode() {
        await this.openForm("fiber.gis.node", false, this.planCreationContext());
    }

    async createSite() {
        await this.openForm("fiber.gis.site");
    }

    async createCable() {
        await this.openForm("fiber.gis.cable", false, this.planCreationContext());
    }

    toggleCableDrawing() {
        if (this.state.cableDraftMode) {
            this.finishCableDraftTracing();
            return;
        }
        this.startCableDrawing(this.selectedNode);
    }

    async startCableDrawing(node = null) {
        if (!this.cableTypes.length) {
            this.notification.add("No hay tipologías de cable activas. Configura una antes de trazar.", { type: "danger" });
            return;
        }
        this.state.cableDraftMode = true;
        this.state.cableDraftChainIds = [];
        this.state.showCableDraftFinalize = false;
        this.state.cableDraftFromNodeId = null;
        this.state.cableDraftViaPoints = [];
        this.state.cableDraftCursor = null;
        this._draftPreviewCursor = null;
        this.state.cableDraftSaving = false;
        this.state.cableDraftFromBocas = [];
        this.state.cableDraftToBocas = [];
        if (!this.cableTypes.some((type) => type.id === Number(this.state.cableDraftTypeId))) {
            this.state.cableDraftTypeId = this.defaultCableTypeId();
        }
        this.state.showNodesLayer = true;
        this.state.showCustomerNodesLayer = true;
        this.state.hiddenNodeKinds = [];
        this.state.filter = "all";
        this.closeContextMenu();
        this.cancelTooltip();
        this.state.selectedCableId = null;
        this.state.selectedSiteId = null;
        if (node && this.hasCoordinates(node)) {
            await this.setCableDraftFromNode(node);
        } else {
            this.notification.add("Selecciona el elemento de origen del cable.", { type: "info" });
        }
    }

    startCableDrawingFromSelected() {
        const node = this.selectedNode;
        if (node) {
            this.startCableDrawing(node);
        }
    }

    async setCableDraftFromNode(node) {
        const nodeId = node.id;
        const requestId = this._cableDraftBocasRequestId = (this._cableDraftBocasRequestId || 0) + 1;
        let availableBocas;
        try {
            availableBocas = await this.availableCableBocas(node);
        } catch (error) {
            this.notification.add(error?.data?.message || "No se han podido consultar las bocas libres.", { type: "danger" });
            return;
        }
        if (!this.state.cableDraftMode || requestId !== this._cableDraftBocasRequestId) {
            return;
        }
        if (!availableBocas.length) {
            this.state.cableDraftMode = false;
            this.notification.add(`No quedan bocas libres en ${node.code || node.name}.`, { type: "warning" });
            return;
        }
        this.state.cableDraftFromNodeId = nodeId;
        this.state.cableDraftToNodeId = null;
        this.state.cableDraftFromBocas = availableBocas;
        this.state.cableDraftToBocas = [];
        this.state.cableDraftFromBoca = null;
        this.state.cableDraftToBoca = null;
        this.state.cableDraftViaPoints = [];
        this.state.cableDraftCursor = [node.latitude, node.longitude];
        this._draftPreviewCursor = null;
        this.selectNode(node);
        this.notification.add(
            "Pulsa sobre el mapa para a\u00f1adir esquinas y sobre otro elemento para elegir las bocas.",
            { type: "info" }
        );
    }

    setCableDraftRouteKind(routeKind) {
        this.state.cableDraftRouteKind = routeKind;
    }

    cancelCableDrawing(notify = true) {
        const wasActive = this.state.cableDraftMode;
        this._cableDraftBocasRequestId = (this._cableDraftBocasRequestId || 0) + 1;
        this.state.cableDraftMode = false;
        this.state.cableDraftFromNodeId = null;
        this.state.cableDraftToNodeId = null;
        this.state.cableDraftViaPoints = [];
        this.state.cableDraftCursor = null;
        this.state.cableDraftFromBoca = null;
        this.state.cableDraftToBoca = null;
        this.state.cableDraftFromBocas = [];
        this.state.cableDraftToBocas = [];
        this._draftPreviewCursor = null;
        this.state.cableDraftSaving = false;
        this.state.cableDraftChainIds = [];
        this.state.cableDraftFinalProfileId = false;
        this.state.showCableDraftFinalize = false;
        this.state.cableDraftFinalizing = false;
        if (wasActive && notify) {
            this.notification.add("Trazado de cable cancelado.", { type: "info" });
        }
    }

    finishCableDraftTracing() {
        if (!this.state.cableDraftChainIds.length) {
            this.cancelCableDrawing();
            return;
        }
        this._cableDraftBocasRequestId = (this._cableDraftBocasRequestId || 0) + 1;
        this.state.cableDraftMode = false;
        this.state.cableDraftFromNodeId = null;
        this.state.cableDraftToNodeId = null;
        this.state.cableDraftViaPoints = [];
        this.state.cableDraftCursor = null;
        this.state.cableDraftFromBoca = null;
        this.state.cableDraftToBoca = null;
        this.state.cableDraftFromBocas = [];
        this.state.cableDraftToBocas = [];
        this._draftPreviewCursor = null;
        this.state.cableDraftFinalProfileId = false;
        this.state.showCableDraftFinalize = true;
        this.state.cableDraftSaving = false;
    }

    cancelCableDraftFinalization() {
        this.state.showCableDraftFinalize = false;
        this.state.cableDraftChainIds = [];
        this.state.cableDraftFinalProfileId = false;
        this.notification.add(
            "Se conservan los cables con la tipología actual. Puedes cambiarla desde sus fichas.",
            { type: "warning" }
        );
    }

    async finalizeCableDraftChain() {
        const profileId = Number(this.state.cableDraftFinalProfileId);
        const cableIds = [...this.state.cableDraftChainIds];
        if (!profileId || !cableIds.length || this.state.cableDraftFinalizing) {
            return;
        }
        this.state.cableDraftFinalizing = true;
        try {
            const result = await this.orm.call(
                "fiber.gis.cable",
                "finalize_map_cable_chain",
                [cableIds, profileId]
            );
            this.state.showCableDraftFinalize = false;
            this.state.cableDraftChainIds = [];
            this.state.cableDraftFinalProfileId = false;
            this.state.cableDraftFinalizing = false;
            await this.loadData();
            const lastCable = this.state.cables.find((item) => item.id === cableIds[cableIds.length - 1]);
            if (lastCable) {
                this.selectCable(lastCable);
            }
            this.notification.add(
                `Trazado finalizado: ${cableIds.length} cable(s) con tipología ${result.profile}.`,
                { type: "success" }
            );
            for (const sangria of result.sangria_results || []) {
                if (sangria.created) {
                    this.notification.add(
                        `Sangría en ${sangria.node}: ${sangria.created} fibras en ${sangria.tray}.` +
                        (sangria.skipped ? ` ${sangria.skipped} pares ocupados se dejaron sin modificar.` : ""),
                        { type: "info" }
                    );
                } else if (sangria.note) {
                    this.notification.add(`${sangria.node}: ${sangria.note}`, { type: "warning" });
                }
            }
            this.cancelCableDrawing(false);
        } catch (error) {
            this.state.cableDraftFinalizing = false;
            this.notification.add(
                error?.data?.message || "No se ha podido aplicar la tipología al trazado.",
                { type: "danger" }
            );
        }
    }

    undoCableDraftPoint() {
        this._draftPreviewCursor = null;
        if ((this.state.cableDraftViaPoints || []).length) {
            this.state.cableDraftViaPoints = this.state.cableDraftViaPoints.slice(0, -1);
            const previous = this.state.cableDraftViaPoints[this.state.cableDraftViaPoints.length - 1];
            const source = this.cableDraftFromNode;
            this.state.cableDraftCursor = previous || (
                source ? [source.latitude, source.longitude] : null
            );
            return;
        }
        if (this.state.cableDraftFromNodeId) {
            this.state.cableDraftFromNodeId = null;
            this.state.cableDraftFromBoca = null;
            this.state.cableDraftFromBocas = [];
            this.state.cableDraftToNodeId = null;
            this.state.cableDraftToBoca = null;
            this.state.cableDraftToBocas = [];
            this.state.cableDraftCursor = null;
            this.notification.add("Selecciona de nuevo el elemento de origen.", { type: "info" });
        }
    }

    addCableDraftPoint(ev) {
        if (!this.state.cableDraftFromNodeId || !this.state.bounds) {
            this.notification.add("Primero selecciona el elemento de origen.", { type: "warning" });
            return;
        }
        const geo = this.screenToGeo(ev.clientX, ev.clientY);
        const point = [
            Number(geo.latitude.toFixed(7)),
            Number(geo.longitude.toFixed(7)),
        ];
        this.state.cableDraftViaPoints = [...this.state.cableDraftViaPoints, point];
        this.state.cableDraftCursor = point;
        this._draftPreviewCursor = null;
    }

    async onCableDraftNodeClick(node) {
        if (this.state.cableDraftSaving) {
            return;
        }
        if (!this.hasCoordinates(node)) {
            this.notification.add("El elemento no tiene coordenadas.", { type: "warning" });
            return;
        }
        if (!this.state.cableDraftFromNodeId) {
            await this.setCableDraftFromNode(node);
            return;
        }
        if (node.id === this.state.cableDraftFromNodeId) {
            this.notification.add("Selecciona un elemento de destino distinto.", { type: "warning" });
            return;
        }

        const requestId = this._cableDraftBocasRequestId = (this._cableDraftBocasRequestId || 0) + 1;
        let availableBocas;
        try {
            availableBocas = await this.availableCableBocas(node);
        } catch (error) {
            this.notification.add(error?.data?.message || "No se han podido consultar las bocas libres.", { type: "danger" });
            return;
        }
        if (!this.state.cableDraftMode || requestId !== this._cableDraftBocasRequestId) {
            return;
        }
        if (!availableBocas.length) {
            this.notification.add(`No quedan bocas libres en ${node.code || node.name}.`, { type: "warning" });
            return;
        }
        this.state.cableDraftToNodeId = node.id;
        this.state.cableDraftToBocas = availableBocas;
        this.state.cableDraftToBoca = null;
    }

    cancelCableDraftDestination() {
        this.state.cableDraftToNodeId = null;
        this.state.cableDraftToBoca = null;
        this.state.cableDraftToBocas = [];
    }

    async saveCableDraft(continueTracing = false) {
        const node = this.cableDraftToNode;
        const fromBoca = Number(this.state.cableDraftFromBoca);
        const toBoca = Number(this.state.cableDraftToBoca);
        if (!node || !fromBoca || !toBoca || this.state.cableDraftSaving) {
            return;
        }
        this.state.cableDraftSaving = true;
        try {
            const result = await this.orm.call(
                "fiber.gis.cable",
                "create_from_map",
                [
                    this.state.cableDraftFromNodeId,
                    node.id,
                    this.state.cableDraftViaPoints.map((point) => [point[0], point[1]]),
                    this.state.plan?.id || false,
                    this.state.cableDraftRouteKind,
                    Number(this.state.cableDraftTypeId) || false,
                    fromBoca,
                    toBoca,
                ]
            );
            const destinationNodeId = node.id;
            this.state.cableDraftChainIds = [...this.state.cableDraftChainIds, result.id];
            await this.loadData();
            const length = Math.round(result.length_m || 0);
            if (continueTracing) {
                const nextSource = this.state.nodes.find((item) => item.id === destinationNodeId);
                if (nextSource) {
                    await this.setCableDraftFromNode(nextSource);
                }
                this.state.cableDraftSaving = false;
                this.notification.add(
                    `Cable creado: ${result.name} (${length} m). Continúa desde ${nextSource?.code || nextSource?.name || "la caja de destino"}.`,
                    { type: "success" }
                );
            } else {
                this.finishCableDraftTracing();
            }
        } catch (error) {
            try {
                const [fromBocas, toBocas] = await Promise.all([
                    this.availableCableBocas(this.cableDraftFromNode),
                    this.availableCableBocas(this.cableDraftToNode),
                ]);
                this.state.cableDraftFromBocas = fromBocas;
                this.state.cableDraftToBocas = toBocas;
                if (!fromBocas.includes(Number(this.state.cableDraftFromBoca))) {
                    this.state.cableDraftFromBoca = null;
                }
                if (!toBocas.includes(Number(this.state.cableDraftToBoca))) {
                    this.state.cableDraftToBoca = null;
                }
            } catch {
                // Se conserva el error original de creación si falla la actualización de opciones.
            }
            this.state.cableDraftSaving = false;
            this.notification.add(
                error?.data?.message || "No se ha podido crear el cable desde el mapa.",
                { type: "danger" }
            );
            console.error("Fiber GIS: error al crear el cable desde el mapa", error);
        }
    }

    onNodeClick(node) {
        if (this.state.cableDraftMode) {
            this.onCableDraftNodeClick(node);
            return;
        }
        this.selectNode(node);
    }

    async openMapRecord(resModel, resId) {
        if (!resId || this.state.cableDraftMode) {
            return;
        }
        const recordKey = `${resModel}-${resId}`;
        const now = Date.now();
        if (
            this._openingMapRecordKey === recordKey ||
            (this._lastOpenedMapRecord?.key === recordKey && now - this._lastOpenedMapRecord.time < 1000)
        ) {
            return;
        }
        this._openingMapRecordKey = recordKey;
        this._lastOpenedMapRecord = { key: recordKey, time: now };
        this.cancelTooltip();
        this.closeContextMenu();
        clearTimeout(this._interactionCommitTimer);
        this.commitInteractionCamera();
        this.saveCamera();
        try {
            await this.action.doAction({
                type: "ir.actions.act_window",
                res_model: resModel,
                res_id: resId,
                views: [[false, "form"]],
                target: "current",
            });
        } finally {
            if (this._openingMapRecordKey === recordKey) {
                this._openingMapRecordKey = null;
            }
        }
    }

    onCableClick(cable) {
        if (!this.state.cableDraftMode) {
            this.selectCable(cable);
        }
    }

    onCableHitPointerDown(ev) {
        if (this.state.cableDraftMode && ev.button !== 2) {
            this.notification.add(
                "Un cable solo puede terminar en un elemento de red. Selecciona el elemento de destino.",
                { type: "warning" }
            );
        }
    }

    planCreationContext(extra = {}) {
        if (!this.state.plan?.id) {
            return extra;
        }
        return {
            ...extra,
            default_deployment_plan_id: this.state.plan.id,
            default_state: "planned",
        };
    }

    round(value) {
        return Math.round(value || 0);
    }

    stateLabel(value) {
        const labels = {
            planned: "Planificado",
            installed: "Instalado",
            active: "Activo",
            maintenance: "Mantenimiento",
            fault: "Incidencia",
            retired: "Retirado",
            done: "Realizado",
            down: "Ca\u00eddo",
            free: "Libre",
            used: "Usado",
            reserved: "Reservado",
        };
        return labels[value] || value || "";
    }

    zoom(delta) {
        clearTimeout(this._interactionCommitTimer);
        this.commitInteractionCamera();
        this.state.scale = Math.max(this.state.scale * delta, 0.000001);
        this.scheduleSaveCamera();
    }

    beginInteractionCamera() {
        if (!this._interactionCamera) {
            this._interactionCamera = {
                scale: this.state.scale,
                offsetX: this.state.offsetX,
                offsetY: this.state.offsetY,
            };
        }
        return this._interactionCamera;
    }

    previewZoomAt(delta, clientX, clientY) {
        if (!this.state.bounds || !this.svg.el) {
            this.zoom(delta);
            return;
        }
        const camera = this.beginInteractionCamera();
        const rect = this.svg.el.getBoundingClientRect();
        const x = clientX - rect.left;
        const y = clientY - rect.top;
        const newScale = Math.max(camera.scale * delta, 0.000001);
        camera.offsetX = x - ((x - camera.offsetX) / camera.scale) * newScale;
        camera.offsetY = y - ((y - camera.offsetY) / camera.scale) * newScale;
        camera.scale = newScale;
        this.applySceneCamera(camera);
        this.updateZoomIndicator(camera);
    }

    applySceneCamera(camera) {
        this._pendingSceneCamera = { ...camera };
        if (this._sceneAnimationFrame) {
            return;
        }
        this._sceneAnimationFrame = requestAnimationFrame(() => {
            this._sceneAnimationFrame = null;
            const target = this._pendingSceneCamera;
            const scene = this.mapScene.el;
            if (!target || !scene) {
                return;
            }
            const ratio = target.scale / this.state.scale;
            const translateX = target.offsetX - ratio * this.state.offsetX;
            const translateY = target.offsetY - ratio * this.state.offsetY;
            scene.style.transform = `matrix(${ratio}, 0, 0, ${ratio}, ${translateX}, ${translateY})`;
        });
    }

    clearSceneTransform() {
        if (this._sceneAnimationFrame) {
            cancelAnimationFrame(this._sceneAnimationFrame);
            this._sceneAnimationFrame = null;
        }
        this._pendingSceneCamera = null;
        if (this.mapScene.el) {
            this.mapScene.el.style.transform = "";
        }
    }

    commitInteractionCamera() {
        const camera = this._interactionCamera;
        if (!camera) {
            return false;
        }
        this._interactionCamera = null;
        this._clearSceneTransformAfterPatch = true;
        this.state.scale = camera.scale;
        this.state.offsetX = camera.offsetX;
        this.state.offsetY = camera.offsetY;
        return true;
    }

    scheduleInteractionCameraCommit(delay = MAP_PAN_COMMIT_IDLE_MS) {
        clearTimeout(this._interactionCommitTimer);
        this._interactionCommitTimer = setTimeout(() => {
            this._interactionCommitTimer = null;
            if (this._panning || this._wheelZooming) {
                return;
            }
            if (this.commitInteractionCamera()) {
                this.scheduleSaveCamera();
            }
        }, delay);
    }

    updateZoomIndicator(camera = this._interactionCamera) {
        if (this.zoomIndicator.el) {
            this.zoomIndicator.el.textContent = this.formatZoomLabel(
                camera?.scale || this.state.scale
            );
        }
    }

    zoomAt(delta, clientX, clientY) {
        if (!this.state.bounds || !this.svg.el) {
            this.zoom(delta);
            return;
        }
        clearTimeout(this._interactionCommitTimer);
        this.commitInteractionCamera();
        const rect = this.svg.el.getBoundingClientRect();
        const x = clientX - rect.left;
        const y = clientY - rect.top;
        const before = {
            x: (x - this.state.offsetX) / this.state.scale + this.state.bounds.minX,
            y: (y - this.state.offsetY) / this.state.scale + this.state.bounds.minY,
        };
        this.state.scale = Math.max(this.state.scale * delta, 0.000001);
        this.state.offsetX = x - (before.x - this.state.bounds.minX) * this.state.scale;
        this.state.offsetY = y - (before.y - this.state.bounds.minY) * this.state.scale;
        this.closeContextMenu();
        this.scheduleSaveCamera();
    }

    pan(dx, dy) {
        clearTimeout(this._interactionCommitTimer);
        this.commitInteractionCamera();
        this.state.offsetX += dx;
        this.state.offsetY += dy;
        this.closeContextMenu();
        this.scheduleSaveCamera();
    }

    mapEventOwner(target) {
        const closest = target?.closest?.bind(target);
        if (!closest) {
            return null;
        }
        const cablePoint = closest(".o_fiber_gis_cable_point");
        if (cablePoint) {
            const cableId = Number(cablePoint.dataset.cableId);
            const pointIndex = Number(cablePoint.dataset.pointIndex);
            const cable = this._cablesById?.get(cableId);
            return cable && Number.isInteger(pointIndex)
                ? { kind: "cable-point", id: cableId, record: cable, pointIndex }
                : null;
        }
        const nodeElement = closest("[data-node-id]");
        if (nodeElement) {
            const id = Number(nodeElement.dataset.nodeId);
            const record = this._nodesById?.get(id);
            return record ? { kind: "node", id, record } : null;
        }
        const siteElement = closest("[data-site-id]");
        if (siteElement) {
            const id = Number(siteElement.dataset.siteId);
            const record = this._sitesById?.get(id);
            return record ? { kind: "site", id, record } : null;
        }
        const cableElement = closest(".o_fiber_gis_cable_hit");
        if (cableElement) {
            const id = Number(cableElement.dataset.cableId);
            const record = this._cablesById?.get(id);
            return record ? { kind: "cable", id, record } : null;
        }
        return null;
    }

    onMapPointerDown(ev) {
        const owner = this.mapEventOwner(ev.target);
        if (this.registerMapPointerDoubleClick(owner, ev)) {
            return;
        }
        if (owner?.kind === "cable-point") {
            this.onCablePointPointerDown(owner.record, { index: owner.pointIndex }, ev);
            return;
        }
        if (owner?.kind === "node") {
            this.onNodePointerDown(owner.record, ev);
            return;
        }
        if (owner?.kind === "site") {
            this.onSitePointerDown(owner.record, ev);
            return;
        }
        if (owner?.kind === "cable") {
            ev.stopPropagation();
            this.onCableHitPointerDown(ev);
            return;
        }
        this.onBackgroundPointerDown(ev);
    }

    registerMapPointerDoubleClick(owner, ev) {
        if (!owner || !["node", "site"].includes(owner.kind)) {
            this._lastMapPointerDown = null;
            return false;
        }
        const now = Date.now();
        const key = `${owner.kind}-${owner.id}`;
        if (this._lastMapPointerDown?.key === key && now - this._lastMapPointerDown.time <= 600) {
            this._lastMapPointerDown = null;
            ev.preventDefault();
            ev.stopPropagation();
            this.openMapRecord(
                owner.kind === "node" ? "fiber.gis.node" : "fiber.gis.site",
                owner.id
            );
            return true;
        }
        this._lastMapPointerDown = { key, time: now };
        return false;
    }

    onMapClick(ev) {
        if (this._suppressMapClickUntil && Date.now() <= this._suppressMapClickUntil) {
            this._suppressMapClickUntil = 0;
            this._lastMapPointerDown = null;
            return;
        }
        this._suppressMapClickUntil = 0;
        const owner = this.mapEventOwner(ev.target);
        if (!owner) {
            return;
        }
        ev.stopPropagation();
        if (owner.kind === "node") {
            this.onNodeClick(owner.record);
        } else if (owner.kind === "site") {
            this.onSiteClick(owner.record);
        } else if (owner.kind === "cable") {
            this.onCableClick(owner.record);
        }
    }

    onMapDoubleClick(ev) {
        const owner = this.mapEventOwner(ev.target);
        if (!owner || !["node", "site", "cable"].includes(owner.kind)) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        this.openMapRecord(
            owner.kind === "node"
                ? "fiber.gis.node"
                : owner.kind === "site"
                    ? "fiber.gis.site"
                    : "fiber.gis.cable",
            owner.id
        );
    }

    onMapPointerOver(ev) {
        const owner = this.mapEventOwner(ev.target);
        const previous = this.mapEventOwner(ev.relatedTarget);
        if (!owner || owner.kind === "cable-point" || (
            previous?.kind === owner.kind && previous.id === owner.id
        )) {
            return;
        }
        this.scheduleTooltip(owner.kind, owner.record, ev);
    }

    onMapPointerOut(ev) {
        const owner = this.mapEventOwner(ev.target);
        const next = this.mapEventOwner(ev.relatedTarget);
        if (owner && next?.kind === owner.kind && next.id === owner.id) {
            return;
        }
        this.cancelTooltip();
    }

    onMapContextMenu(ev) {
        const owner = this.mapEventOwner(ev.target);
        ev.preventDefault();
        if (owner?.kind === "cable") {
            ev.stopPropagation();
            this.onCableContextMenu(owner.record, ev);
            return;
        }
        this.onContextMenu(ev);
    }

    onBackgroundPointerDown(ev) {
        if (ev.button === 2) {
            return;
        }
        if (this.state.cableDraftMode) {
            ev.stopPropagation();
            this.cancelTooltip();
            this.addCableDraftPoint(ev);
            return;
        }
        this.cancelTooltip();
        this.closeContextMenu();
        this._panning = true;
        clearTimeout(this._interactionCommitTimer);
        const hadPendingCamera = Boolean(this._interactionCamera);
        const camera = this.beginInteractionCamera();
        if (this.svg.el?.setPointerCapture) {
            this.svg.el.setPointerCapture(ev.pointerId);
        }
        this._panPointerStart = {
            x: ev.clientX,
            y: ev.clientY,
            offsetX: camera.offsetX,
            offsetY: camera.offsetY,
            moved: false,
            hadPendingCamera,
        };
    }

    onWheel(ev) {
        const unit = ev.deltaMode === 1
            ? 16
            : ev.deltaMode === 2
                ? this.state.viewHeight
                : 1;
        const wheelPixels = Math.max(Math.min(ev.deltaY * unit, 120), -120);
        const delta = Math.exp(-wheelPixels * 0.0015);
        if (!this._wheelZooming) {
            this.cancelTooltip();
            this.closeContextMenu();
        }
        clearTimeout(this._interactionCommitTimer);
        this._wheelZooming = true;
        this.previewZoomAt(delta, ev.clientX, ev.clientY);
        clearTimeout(this._wheelTimer);
        this._wheelTimer = setTimeout(() => {
            this._wheelZooming = false;
            this.scheduleInteractionCameraCommit(0);
        }, MAP_INTERACTION_IDLE_MS);
    }

    onContextMenu(ev) {
        if (this.state.cableDraftMode) {
            this.undoCableDraftPoint();
            return;
        }
        const geo = this.screenToGeo(ev.clientX, ev.clientY);
        const rect = this.svg.el.getBoundingClientRect();
        this.state.contextMenu = {
            x: ev.clientX - rect.left,
            y: ev.clientY - rect.top,
            latitude: Number(geo.latitude.toFixed(7)),
            longitude: Number(geo.longitude.toFixed(7)),
        };
    }

    onCableContextMenu(cable, ev) {
        if (this.state.cableDraftMode) {
            this.undoCableDraftPoint();
            return;
        }
        this.selectCable(cable);
        const geo = this.screenToGeo(ev.clientX, ev.clientY);
        const rect = this.svg.el.getBoundingClientRect();
        const clickPoint = {
            x: ev.clientX - rect.left,
            y: ev.clientY - rect.top,
        };
        this.state.contextMenu = {
            x: clickPoint.x,
            y: clickPoint.y,
            latitude: Number(geo.latitude.toFixed(7)),
            longitude: Number(geo.longitude.toFixed(7)),
            cableId: cable.id,
            segmentIndex: this.closestCableSegmentIndex(cable, clickPoint),
            insertIndex: this.closestCableSegmentIndex(cable, clickPoint) + 1,
        };
    }

    async setCableRouteKindAtContext(routeKind) {
        const point = this.state.contextMenu;
        const cable = this.state.cables.find((item) => item.id === point?.cableId);
        if (!cable) {
            this.closeContextMenu();
            return;
        }
        const historyAction = this.createHistoryAction(
            "fiber.gis.cable",
            cable,
            ["route_segment_kinds"],
            `Cambiar tramo de ${cable.code || cable.name || `Cable ${cable.id}`}`
        );
        const segmentKinds = this.cableSegmentKinds(cable);
        const segmentIndex = Math.max(0, Math.min(point.segmentIndex || 0, segmentKinds.length - 1));
        segmentKinds[segmentIndex] = routeKind;
        cable.route_segment_kinds = JSON.stringify(segmentKinds);
        this.closeContextMenu();
        await this.orm.write("fiber.gis.cable", [cable.id], {
            route_segment_kinds: cable.route_segment_kinds,
        });
        this.finishHistoryAction(historyAction, cable);
        this.notification.add(`Tramo marcado como ${this.routeKindLabel(routeKind)}`, { type: "success" });
    }

    createHistoryAction(model, record, fields, label) {
        return {
            model,
            recordId: record.id,
            fields: [...fields],
            label,
            before: this.historyValues(record, fields),
            after: null,
        };
    }

    historyValues(record, fields) {
        return Object.fromEntries(fields.map((fieldName) => [
            fieldName,
            record[fieldName] ?? false,
        ]));
    }

    finishHistoryAction(action, record) {
        if (!action || !record) {
            return;
        }
        action.after = this.historyValues(record, action.fields);
        if (JSON.stringify(action.before) === JSON.stringify(action.after)) {
            return;
        }
        this._undoStack.push(action);
        if (this._undoStack.length > MAP_HISTORY_LIMIT) {
            this._undoStack.shift();
        }
        this._redoStack = [];
        this.syncHistoryState();
    }

    syncHistoryState() {
        this.state.undoCount = this._undoStack.length;
        this.state.redoCount = this._redoStack.length;
    }

    historyRecord(action) {
        const collection = {
            "fiber.gis.site": this.state.sites,
            "fiber.gis.node": this.state.nodes,
            "fiber.gis.cable": this.state.cables,
        }[action.model] || [];
        return collection.find((record) => record.id === action.recordId);
    }

    async applyHistoryAction(action, values) {
        await this.orm.write(action.model, [action.recordId], values);
        const record = this.historyRecord(action);
        if (record) {
            Object.assign(record, values);
            if (action.model === "fiber.gis.node") {
                if (this.hasCoordinates(record)) {
                    if (this.state.pendingNodePlacementId === record.id) {
                        this.state.pendingNodePlacementId = 0;
                    }
                } else {
                    this.state.showNodesLayer = true;
                    this.state.pendingNodePlacementId = record.id;
                    this.selectNode(record);
                }
            }
        }
        if (action.model !== "fiber.gis.site") {
            await this.refreshPlanMetrics();
        }
    }

    async undoLastMapEdit() {
        if (this.state.historyBusy || !this._undoStack.length) {
            return;
        }
        const action = this._undoStack.pop();
        this.state.historyBusy = true;
        try {
            await this.applyHistoryAction(action, action.before);
            this._redoStack.push(action);
            this.notification.add(`Deshecho: ${action.label}`, { type: "success" });
        } catch {
            this._undoStack.push(action);
            this.notification.add("No se ha podido deshacer el cambio.", { type: "danger" });
        } finally {
            this.state.historyBusy = false;
            this.syncHistoryState();
        }
    }

    async redoLastMapEdit() {
        if (this.state.historyBusy || !this._redoStack.length) {
            return;
        }
        const action = this._redoStack.pop();
        this.state.historyBusy = true;
        try {
            await this.applyHistoryAction(action, action.after);
            this._undoStack.push(action);
            this.notification.add(`Rehecho: ${action.label}`, { type: "success" });
        } catch {
            this._redoStack.push(action);
            this.notification.add("No se ha podido rehacer el cambio.", { type: "danger" });
        } finally {
            this.state.historyBusy = false;
            this.syncHistoryState();
        }
    }

    closestCableSegmentIndex(cable, clickPoint) {
        const points = this.cablePoints(cable);
        if (points.length < 2) {
            return 0;
        }
        let bestIndex = 0;
        let bestDistance = Infinity;
        for (let index = 0; index < points.length - 1; index++) {
            const distance = this.distanceToSegment(clickPoint, points[index], points[index + 1]);
            if (distance < bestDistance) {
                bestDistance = distance;
                bestIndex = index;
            }
        }
        return bestIndex;
    }

    distanceToSegment(point, start, end) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        if (!dx && !dy) {
            return Math.hypot(point.x - start.x, point.y - start.y);
        }
        const t = Math.max(0, Math.min(1, ((point.x - start.x) * dx + (point.y - start.y) * dy) / (dx * dx + dy * dy)));
        const projectedX = start.x + t * dx;
        const projectedY = start.y + t * dy;
        return Math.hypot(point.x - projectedX, point.y - projectedY);
    }

    closeContextMenu() {
        this.state.contextMenu = null;
    }

    async reverseGeocodeCoordinates(latitude, longitude) {
        try {
            const result = await this.orm.call(
                "fiber.gis.site",
                "reverse_geocode_coordinates",
                [latitude, longitude]
            );
            if (!result?.address && result?.warning) {
                this.notification.add(result.warning, { type: "warning" });
            }
            return result?.address || "";
        } catch {
            this.notification.add(
                "No se ha podido obtener la direcci\u00f3n. Las coordenadas se conservar\u00e1n.",
                { type: "warning" }
            );
            return "";
        }
    }

    async createSiteAtContext() {
        const point = this.state.contextMenu;
        this.closeContextMenu();
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "fiber.gis.site",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_latitude: point.latitude,
                default_longitude: point.longitude,
                default_state: "planned",
            },
        });
    }

    async createNodeAtContext() {
        const point = this.state.contextMenu;
        this.closeContextMenu();
        const address = await this.reverseGeocodeCoordinates(
            point.latitude,
            point.longitude
        );
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "fiber.gis.node",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_latitude: point.latitude,
                default_longitude: point.longitude,
                default_address: address,
                default_state: "planned",
                default_deployment_plan_id: this.state.plan?.id || false,
            },
        });
    }

    async addCablePointAtContext() {
        const point = this.state.contextMenu;
        const cable = this.state.cables.find((item) => item.id === point?.cableId);
        if (!cable) {
            this.closeContextMenu();
            return;
        }
        const historyAction = this.createHistoryAction(
            "fiber.gis.cable",
            cable,
            ["geometry_geojson", "route_segment_kinds"],
            `A\u00f1adir punto a ${cable.code || cable.name || `Cable ${cable.id}`}`
        );
        const geoPoints = this.cableGeoPoints(cable).map((geoPoint) => [...geoPoint]);
        const insertIndex = Math.max(1, Math.min(point.insertIndex || geoPoints.length - 1, geoPoints.length - 1));
        const segmentKinds = this.cableSegmentKinds(cable);
        const splitIndex = insertIndex - 1;
        const splitKind = segmentKinds[splitIndex] || cable.route_kind || "underground";
        geoPoints.splice(insertIndex, 0, [point.latitude, point.longitude]);
        segmentKinds.splice(splitIndex, 1, splitKind, splitKind);
        cable.geometry_geojson = this.cableGeometryValue(cable, geoPoints);
        cable.route_segment_kinds = JSON.stringify(segmentKinds);
        this.closeContextMenu();
        await this.orm.write("fiber.gis.cable", [cable.id], {
            geometry_geojson: cable.geometry_geojson,
            route_segment_kinds: cable.route_segment_kinds,
        });
        this.finishHistoryAction(historyAction, cable);
        await this.refreshPlanMetrics();
        this.notification.add("Punto a\u00f1adido al cable", { type: "success" });
    }

    pointerGeo(clientX, clientY) {
        const geo = this.screenToGeo(clientX, clientY);
        return [
            Number(geo.latitude.toFixed(7)),
            Number(geo.longitude.toFixed(7)),
        ];
    }

    captureMapPointer(ev) {
        if (this.svg.el?.setPointerCapture) {
            this.svg.el.setPointerCapture(ev.pointerId);
        }
    }

    relationId(relation) {
        return Number(Array.isArray(relation) ? relation[0] : relation) || 0;
    }

    connectedCablePreviews(nodeId) {
        return this.state.cables
            .filter((cable) => (
                this.relationId(cable.from_node_id) === nodeId ||
                this.relationId(cable.to_node_id) === nodeId
            ))
            .map((cable) => ({
                cable,
                moveStart: this.relationId(cable.from_node_id) === nodeId,
                moveEnd: this.relationId(cable.to_node_id) === nodeId,
                points: this.cableGeoPoints(cable).map((point) => [...point]),
            }));
    }

    previewCablePaths(cableId, geoPoints) {
        const points = geoPoints.map((point) => this.mapPoint(point[0], point[1]));
        const selector = `[data-cable-id="${Number(cableId)}"]`;
        for (const path of this.svg.el?.querySelectorAll(selector) || []) {
            const index = Number(path.dataset.segmentIndex);
            if (!Number.isInteger(index) || !points[index] || !points[index + 1]) {
                continue;
            }
            path.setAttribute(
                "d",
                `M ${points[index].x} ${points[index].y} L ${points[index + 1].x} ${points[index + 1].y}`
            );
        }
        for (let index = 1; index < points.length - 1; index += 1) {
            const control = this.svg.el?.querySelector(
                `[data-cable-point="${Number(cableId)}-${index}"]`
            );
            if (control) {
                control.setAttribute("cx", points[index].x);
                control.setAttribute("cy", points[index].y);
            }
        }
    }

    previewMarker(kind, recordId, geo) {
        const point = this.mapPoint(geo[0], geo[1]);
        const marker = this.svg.el?.querySelector(`[data-${kind}-id="${Number(recordId)}"]`);
        marker?.setAttribute("transform", `translate(${point.x},${point.y})`);
    }

    applyDragPreview(clientX, clientY) {
        const preview = this._dragPreview;
        if (!preview || !this.state.bounds) {
            return;
        }
        const geo = this.pointerGeo(clientX, clientY);
        preview.geo = geo;
        if (preview.kind === "cable") {
            const points = preview.basePoints.map((point) => [...point]);
            points[preview.index] = geo;
            preview.points = points;
            this.previewCablePaths(preview.cable.id, points);
            return;
        }
        this.previewMarker(preview.kind, preview.record.id, geo);
        if (preview.kind === "node") {
            for (const connected of preview.connectedCables) {
                const points = connected.points.map((point) => [...point]);
                if (connected.moveStart && points.length) {
                    points[0] = geo;
                }
                if (connected.moveEnd && points.length) {
                    points[points.length - 1] = geo;
                }
                this.previewCablePaths(connected.cable.id, points);
            }
        }
    }

    applyCableDraftPreview(clientX, clientY) {
        if (!this.state.cableDraftFromNodeId || !this.state.bounds) {
            return;
        }
        const cursor = this.pointerGeo(clientX, clientY);
        this._draftPreviewCursor = cursor;
        const node = this.cableDraftFromNode;
        if (!node) {
            return;
        }
        const geoPoints = [
            [node.latitude, node.longitude],
            ...(this.state.cableDraftViaPoints || []),
            cursor,
        ];
        const points = geoPoints.map((point) => this.mapPoint(point[0], point[1]));
        const path = points
            .map((point, index) => `${index ? "L" : "M"} ${point.x} ${point.y}`)
            .join(" ");
        this.svg.el?.querySelector("[data-cable-draft-path]")?.setAttribute("d", path);
    }

    queuePointerPreview(kind, ev) {
        this._pendingPointerPreview = { kind, clientX: ev.clientX, clientY: ev.clientY };
        if (this._dragAnimationFrame) {
            return;
        }
        this._dragAnimationFrame = requestAnimationFrame(() => {
            this._dragAnimationFrame = null;
            const pending = this._pendingPointerPreview;
            this._pendingPointerPreview = null;
            if (!pending) {
                return;
            }
            if (pending.kind === "draft") {
                this.applyCableDraftPreview(pending.clientX, pending.clientY);
            } else {
                this.applyDragPreview(pending.clientX, pending.clientY);
            }
        });
    }

    flushPointerPreview() {
        if (this._dragAnimationFrame) {
            cancelAnimationFrame(this._dragAnimationFrame);
            this._dragAnimationFrame = null;
        }
        const pending = this._pendingPointerPreview;
        this._pendingPointerPreview = null;
        if (!pending) {
            return;
        }
        if (pending.kind === "draft") {
            this.applyCableDraftPreview(pending.clientX, pending.clientY);
        } else {
            this.applyDragPreview(pending.clientX, pending.clientY);
        }
    }

    onCablePointPointerDown(cable, point, ev) {
        if (ev.button === 2) {
            return;
        }
        ev.stopPropagation();
        if (this.state.cableDraftMode) {
            this.addCableDraftPoint(ev);
            return;
        }
        this.cancelTooltip();
        this.closeContextMenu();
        this.selectCable(cable);
        this._dragHistoryAction = this.createHistoryAction(
            "fiber.gis.cable",
            cable,
            ["geometry_geojson"],
            `Mover punto de ${cable.code || cable.name || `Cable ${cable.id}`}`
        );
        this._draggingCablePoint = {
            cableId: cable.id,
            index: point.index,
        };
        this._dragPreview = {
            kind: "cable",
            cable,
            index: point.index,
            basePoints: this.cableGeoPoints(cable).map((geoPoint) => [...geoPoint]),
            points: null,
            geo: null,
        };
        this._dragPointerStart = { x: ev.clientX, y: ev.clientY, moved: false };
        this.captureMapPointer(ev);
    }

    onSitePointerDown(site, ev) {
        if (ev.button === 2) {
            return;
        }
        ev.stopPropagation();
        if (this.state.cableDraftMode) {
            return;
        }
        this.cancelTooltip();
        this.selectSite(site);
        this._dragHistoryAction = this.createHistoryAction(
            "fiber.gis.site",
            site,
            ["latitude", "longitude"],
            `Mover ${site.code || site.name || `Sitio ${site.id}`}`
        );
        this._draggingSiteId = site.id;
        this._dragPreview = { kind: "site", record: site, geo: [site.latitude, site.longitude] };
        this._dragPointerStart = { x: ev.clientX, y: ev.clientY, moved: false };
        this.captureMapPointer(ev);
    }

    onSiteClick(site) {
        if (!this.state.cableDraftMode) {
            this.selectSite(site);
        }
    }

    onNodePointerDown(node, ev) {
        if (ev.button === 2) {
            return;
        }
        ev.stopPropagation();
        this.cancelTooltip();
        if (this.state.cableDraftMode) {
            return;
        }
        this.selectNode(node);
        this._dragHistoryAction = this.createHistoryAction(
            "fiber.gis.node",
            node,
            ["latitude", "longitude", "address"],
            `Mover ${node.code || node.name || `Elemento ${node.id}`}`
        );
        this._draggingNodeId = node.id;
        const needsPlacement = !this.hasCoordinates(node);
        const initialGeo = needsPlacement
            ? this.pointerGeo(ev.clientX, ev.clientY)
            : [node.latitude, node.longitude];
        this._dragPreview = {
            kind: "node",
            record: node,
            geo: initialGeo,
            connectedCables: this.connectedCablePreviews(node.id),
        };
        if (needsPlacement) {
            this.previewMarker("node", node.id, initialGeo);
        }
        this._dragPointerStart = {
            x: ev.clientX,
            y: ev.clientY,
            moved: needsPlacement,
        };
        this.captureMapPointer(ev);
    }

    onPointerMove(ev) {
        if (this.state.cableDraftMode && this.state.cableDraftFromNodeId && this.state.bounds) {
            this.queuePointerPreview("draft", ev);
            return;
        }
        if (this._panning && this._panPointerStart) {
            const deltaX = ev.clientX - this._panPointerStart.x;
            const deltaY = ev.clientY - this._panPointerStart.y;
            if (!this._panPointerStart.moved && Math.hypot(deltaX, deltaY) < 3) {
                return;
            }
            this._panPointerStart.moved = true;
            const camera = this.beginInteractionCamera();
            camera.offsetX = this._panPointerStart.offsetX + deltaX;
            camera.offsetY = this._panPointerStart.offsetY + deltaY;
            this.applySceneCamera(camera);
            return;
        }
        if (
            this._dragPointerStart
            && !this._dragPointerStart.moved
            && (this._draggingSiteId || this._draggingNodeId || this._draggingCablePoint)
        ) {
            const distance = Math.hypot(
                ev.clientX - this._dragPointerStart.x,
                ev.clientY - this._dragPointerStart.y
            );
            if (distance < 5) {
                return;
            }
            this._dragPointerStart.moved = true;
        }
        if (this._draggingCablePoint && this.state.bounds) {
            this.queuePointerPreview("drag", ev);
            return;
        }
        if ((!this._draggingSiteId && !this._draggingNodeId) || !this.state.bounds) {
            return;
        }
        this.queuePointerPreview("drag", ev);
    }

    async onPointerUp(ev) {
        this.flushPointerPreview();
        const wasPanning = this._panning;
        const panMoved = Boolean(this._panPointerStart?.moved);
        const hadPendingCamera = Boolean(this._panPointerStart?.hadPendingCamera);
        this._panning = false;
        this._panPointerStart = null;
        if (ev?.pointerId !== undefined && this.svg.el?.hasPointerCapture?.(ev.pointerId)) {
            this.svg.el.releasePointerCapture(ev.pointerId);
        }
        if (wasPanning && panMoved) {
            this.scheduleInteractionCameraCommit();
        } else if (wasPanning && hadPendingCamera) {
            this.scheduleInteractionCameraCommit(0);
        } else if (wasPanning) {
            this._interactionCamera = null;
            this.clearSceneTransform();
        }
        const moved = Boolean(this._dragPointerStart?.moved);
        const preview = this._dragPreview;
        const draggingSiteId = this._draggingSiteId;
        const draggingNodeId = this._draggingNodeId;
        const draggingCablePoint = this._draggingCablePoint;
        const dragHistoryAction = this._dragHistoryAction;
        this._draggingSiteId = null;
        this._draggingNodeId = null;
        this._draggingCablePoint = null;
        this._dragPointerStart = null;
        this._dragPreview = null;
        this._dragHistoryAction = null;
        if (moved) {
            this._lastMapPointerDown = null;
        }
        this._suppressMapClickUntil = moved ? Date.now() + 250 : 0;

        if (draggingSiteId && moved && preview?.geo) {
            const site = this.state.sites.find((item) => item.id === draggingSiteId);
            site.latitude = preview.geo[0];
            site.longitude = preview.geo[1];
            await this.orm.write("fiber.gis.site", [site.id], {
                latitude: site.latitude,
                longitude: site.longitude,
            });
            this.finishHistoryAction(dragHistoryAction, site);
            this.notification.add("Coordenadas del sitio guardadas", { type: "success" });
        } else if (draggingNodeId && moved && preview?.geo) {
            const node = this.state.nodes.find((item) => item.id === draggingNodeId);
            node.latitude = preview.geo[0];
            node.longitude = preview.geo[1];
            await this.orm.write("fiber.gis.node", [node.id], {
                latitude: node.latitude,
                longitude: node.longitude,
            });
            let addressAdded = false;
            if (!node.address) {
                const address = await this.reverseGeocodeCoordinates(
                    node.latitude,
                    node.longitude
                );
                if (address) {
                    node.address = address;
                    await this.orm.write("fiber.gis.node", [node.id], { address });
                    addressAdded = true;
                }
            }
            await this.refreshPlanMetrics();
            if (this.state.pendingNodePlacementId === node.id) {
                this.state.pendingNodePlacementId = 0;
            }
            this.finishHistoryAction(dragHistoryAction, node);
            this.notification.add(
                addressAdded ? "Coordenadas y direcci\u00f3n guardadas" : "Coordenadas guardadas",
                { type: "success" }
            );
        } else if (draggingCablePoint && moved && preview?.points) {
            const cable = this.state.cables.find((item) => item.id === draggingCablePoint.cableId);
            cable.geometry_geojson = this.cableGeometryValue(cable, preview.points);
            await this.orm.write("fiber.gis.cable", [cable.id], {
                geometry_geojson: cable.geometry_geojson,
            });
            this.finishHistoryAction(dragHistoryAction, cable);
            await this.refreshPlanMetrics();
            this.notification.add("Punto del cable guardado", { type: "success" });
        }
        if (!wasPanning) {
            this.saveCamera();
        }
    }
}

registry.category("actions").add("fiber_gis.map_action", FiberGisMap, { force: true });
console.info("Fiber GIS: accion fiber_gis.map_action registrada");
