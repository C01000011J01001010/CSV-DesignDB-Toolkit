import os
import json
from datetime import datetime

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>__PROJECT_NAME__ - CSV DesignDB ERD Viewer</title>
<script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
    :root {
        --bg-main: #1E1E1E;
        --bg-bar: #252526;
        --bg-input: #2D2D2D;
        --border-color: #3E3E42;
        --text-main: #D4D4D4;
        --text-bright: #FFFFFF;
        --accent: #007ACC;
        --accent-hover: #0098FF;
        --error: #DC3545;
        --pk-color: #FFD700;
        --fk-color: #00FF66;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
        background-color: var(--bg-main);
        color: var(--text-main);
        font-family: 'Malgun Gothic', 'Segoe UI', Consolas, sans-serif;
        overflow: hidden;
        display: flex;
        flex-direction: column;
        height: 100vh;
        height: 100dvh;
        -webkit-user-select: none;
        user-select: none;
    }

    .top-navbar {
        background-color: var(--bg-bar);
        border-bottom: 1px solid var(--border-color);
        height: 48px;
        min-height: 48px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 16px;
        z-index: 20;
    }
    .brand {
        font-size: 15px;
        font-weight: bold;
        color: var(--text-bright);
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .brand span.proj {
        color: var(--fk-color);
        font-family: Consolas, monospace;
    }
    .btn-toggle-menu {
        background-color: var(--bg-input);
        color: var(--text-bright);
        border: 1px solid #555;
        border-radius: 4px;
        padding: 6px 12px;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .options-panel {
        background-color: var(--bg-bar);
        border-bottom: 1px solid var(--border-color);
        padding: 12px 16px;
        display: none; 
        flex-wrap: wrap;
        gap: 12px;
        z-index: 19;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        max-height: 50vh;
        overflow-y: auto;
        position: absolute;
        top: 48px;
        left: 0;
        right: 0;
    }
    .options-panel.show {
        display: flex;
    }

    .control-group {
        display: flex;
        align-items: center;
        gap: 8px;
        background: var(--bg-main);
        padding: 6px 12px;
        border-radius: 4px;
        border: 1px solid var(--border-color);
        flex: 1 1 auto;
        min-width: 200px;
    }
    .control-group label {
        font-size: 12px;
        color: #CCCCCC;
        font-weight: bold;
        cursor: pointer;
        user-select: none;
        white-space: nowrap;
    }
    select, input[type="text"] {
        background-color: var(--bg-input);
        color: var(--text-bright);
        border: 1px solid #555555;
        padding: 6px 10px;
        border-radius: 3px;
        font-family: 'Malgun Gothic', Consolas, sans-serif;
        font-size: 13px;
        outline: none;
        flex: 1;
        min-width: 0;
    }
    select:focus, input[type="text"]:focus {
        border-color: var(--accent);
    }
    button.btn {
        background-color: var(--accent);
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 4px;
        font-size: 13px;
        font-weight: bold;
        cursor: pointer;
        transition: background 0.15s;
        white-space: nowrap;
    }
    button.btn:active { background-color: var(--accent-hover); }

    .main-wrap {
        flex: 1;
        display: flex;
        position: relative;
        overflow: hidden;
    }
    #network-container {
        flex: 1;
        height: 100%;
        background-color: var(--bg-main);
        background-image: radial-gradient(var(--bg-input) 1px, transparent 1px);
        background-size: 24px 24px;
        outline: none;
        touch-action: none;
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        user-select: none;
    }
    
    .vis-network, .vis-network canvas {
        outline: none;
        touch-action: none;
        -webkit-touch-callout: none;
        -webkit-user-select: none;
        user-select: none;
    }

    /* 하단 상태 바 (세로모드/PC 표시, 가로모드에서만 숨김) */
    .status-bar {
        background-color: var(--bg-input);
        border-top: 1px solid var(--border-color);
        padding: 6px 20px;
        font-size: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #BBBBBB;
        z-index: 10;
        flex-wrap: wrap;
        gap: 8px;
    }
    .legend {
        display: flex;
        gap: 18px;
        align-items: center;
        flex-wrap: wrap;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 6px;
        white-space: nowrap;
    }
    .dot { width: 12px; height: 12px; border-radius: 2px; display: inline-block; }

    .overlay {
        display: none;
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        background-color: rgba(0,0,0,0.5);
        z-index: 14;
    }
    .overlay.show {
        display: block;
    }

    .info-panel {
        background-color: var(--bg-bar);
        border-left: 1px solid var(--border-color);
        display: flex;
        flex-direction: column;
        overflow-y: auto;
        padding: 16px;
        z-index: 15;
    }

    /* PC 뷰: 우측 사이드바 고정 */
    @media (min-width: 901px) {
        .info-panel {
            width: 400px;
            height: 100%;
            display: flex !important; 
            position: static !important;
            transform: none !important;
        }
        .btn-close-panel { display: none; }
        .btn-toggle-menu { display: none; }
        .options-panel {
            position: static;
            display: flex;
            box-shadow: none;
            max-height: none;
        }
    }

    /* 모바일 뷰: 바텀 시트 팝업 */
    @media (max-width: 900px) {
        .info-panel {
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            max-height: 80%; 
            height: auto;
            min-height: 40%;
            border-left: none;
            border-top: 2px solid var(--accent);
            border-radius: 16px 16px 0 0;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.5);
            transform: translateY(100%);
            transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        .info-panel.open {
            transform: translateY(0);
        }
        .btn-close-panel {
            position: absolute;
            top: 12px;
            right: 16px;
            background: var(--bg-input);
            border: 1px solid #555;
            color: #FFF;
            border-radius: 50%;
            width: 32px;
            height: 32px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 16;
        }
    }

    .info-panel h3 {
        font-size: 16px;
        color: var(--pk-color);
        margin-bottom: 8px;
        padding-right: 36px;
        word-break: break-all;
    }
    .meta-badge {
        font-size: 12px;
        color: #AAAAAA;
        margin-bottom: 14px;
        font-family: Consolas, monospace;
        line-height: 1.5;
    }
    .section-title {
        font-size: 14px;
        font-weight: bold;
        color: var(--fk-color);
        margin: 16px 0 8px 0;
        border-bottom: 1px solid var(--border-color);
        padding-bottom: 6px;
    }
    .col-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        font-family: Consolas, 'Malgun Gothic', monospace;
    }
    .col-table th, .col-table td {
        border: 1px solid var(--border-color);
        padding: 8px;
        text-align: left;
        vertical-align: top;
        word-break: break-word;
    }
    .col-table th {
        background-color: var(--bg-input);
        color: #CCCCCC;
    }
    .badge-pk { color: var(--pk-color); font-weight: bold; white-space: nowrap; }
    .badge-fk { color: var(--fk-color); font-weight: bold; white-space: nowrap; }
    .badge-type { color: #569CD6; }
    .badge-const { color: #CE9178; font-size: 11px; display: block; margin-top: 4px; }
    
    .err-box {
        background-color: rgba(220, 53, 69, 0.15);
        border: 1px solid var(--error);
        color: #FF7B88;
        padding: 10px;
        border-radius: 6px;
        font-size: 12px;
        margin-bottom: 8px;
        line-height: 1.4;
    }
    .ok-box {
        background-color: rgba(40, 167, 69, 0.15);
        border: 1px solid #28A745;
        color: #5CD679;
        padding: 10px;
        border-radius: 6px;
        font-size: 12px;
    }

    /* 가로 모드에서 하단 바 숨김 */
    @media (max-height: 450px) {
        .top-navbar { height: 36px; min-height: 36px; }
        .status-bar { display: none; }
        .options-panel { top: 36px; }
        .info-panel { max-height: 95%; }
    }
</style>
</head>
<body>

<div class="top-navbar">
    <div class="brand">
        📊 ERD <span class="proj">[__PROJECT_NAME__]</span>
    </div>
    <button class="btn-toggle-menu" onclick="toggleOptions()">
        ⚙️ 설정 / 검색 ▼
    </button>
</div>

<div class="options-panel" id="optionsPanel">
    <div class="control-group">
        <label for="levelSelect">표시 단계:</label>
        <select id="levelSelect" onchange="updateGraphLevel()">
            <option value="1">Level 1: 테이블명 (구조 조망)</option>
            <option value="2">Level 2: PK / FK 컬럼</option>
            <option value="3" selected>Level 3: PK/FK + 타입 (기본)</option>
            <option value="4">Level 4: 전체 컬럼 + 타입</option>
            <option value="5">Level 5: 전체 스키마 (상세 제약조건)</option>
        </select>
    </div>

    <div class="control-group">
        <label for="searchInput">🔍 검색:</label>
        <input type="text" id="searchInput" list="tableList" placeholder="테이블명..." oninput="onSearchTable()">
        <datalist id="tableList"></datalist>
    </div>

    <div class="control-group">
        <input type="checkbox" id="chkHideIsolated" onchange="updateGraphLevel()">
        <label for="chkHideIsolated">고립 노드 숨김</label>
    </div>

    <div class="control-group">
        <input type="checkbox" id="chkPhysics" checked onchange="togglePhysics()">
        <label for="chkPhysics">물리엔진(자동배치)</label>
    </div>

    <button class="btn" onclick="fitNetwork()">🔄 화면 맞춤</button>
</div>

<div class="main-wrap">
    <div id="network-container"></div>
    <div class="overlay" id="overlay" onclick="onOverlayClick(event)"></div>
    <div class="info-panel" id="infoPanel">
        <button class="btn-close-panel" onclick="closeInfoPanel()">X</button>
        <h3>📌 정보 확인</h3>
        <div class="meta-badge"><span id="sb-path">노드나 화살표를 선택해주세요.</span><br><span id="sb-rows"></span></div>
        <div id="sidebar-content"></div>
    </div>
</div>

<div class="status-bar">
    <div class="legend">
        <div class="legend-item"><span class="dot" style="background:#007ACC;"></span> 정상 테이블</div>
        <div class="legend-item"><span class="dot" style="background:#DC3545;"></span> 위반/유령</div>
        <div class="legend-item"><span class="dot" style="background:transparent;border:2px solid #FFD700;"></span> 선택됨(강조)</div>
        <div class="legend-item"><span style="color:#FFD700;font-weight:bold;">🔑</span> PK</div>
        <div class="legend-item"><span style="color:#00FF66;font-weight:bold;">🔗</span> FK</div>
        <div class="legend-item"><span style="color:#00E5FF;font-weight:bold;">🎨</span> AssetID</div>
        <div class="legend-item"><span style="color:#00E5FF;font-weight:bold;">━━▶</span> 정상참조</div>
        <div class="legend-item"><span style="color:#FF4444;font-weight:bold;">┅┅▶</span> 깨진참조</div>
    </div>
    <div id="stats-info">생성 시각: __GENERATED_AT__</div>
</div>

<script>
const rawData = __GRAPH_JSON__;

let network = null;
let nodesDataset = null;
let edgesDataset = null;
let panelOpenedAt = 0;
// 💡 현재 선택된 테이블(Node) 및 참조 화살표(Edge) ID를 모두 추적
let selectedNodeId = null;
let selectedEdgeId = null;

function escapeXml(unsafe) {
    return String(unsafe)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&apos;");
}

function toggleOptions() {
    const p = document.getElementById("optionsPanel");
    if (p.classList.contains("show")) p.classList.remove("show");
    else p.classList.add("show");
}

function onOverlayClick(e) {
    if (Date.now() - panelOpenedAt < 400) {
        if (e && e.cancelable) e.preventDefault();
        if (e && e.stopPropagation) e.stopPropagation();
        return;
    }
    closeInfoPanel();
}

function setSelectedNodeHighlight(nextNodeId) {
    if (!nodesDataset) {
        selectedNodeId = nextNodeId;
        return;
    }
    const level = parseInt(document.getElementById("levelSelect").value, 10);
    const prevNodeId = selectedNodeId;
    selectedNodeId = nextNodeId;

    const updates = [];
    if (prevNodeId && prevNodeId !== nextNodeId && nodesDataset.get(prevNodeId)) {
        const prevNodeData = rawData.nodes.find(n => n.id === prevNodeId);
        if (prevNodeData) {
            updates.push({
                id: prevNodeId,
                image: buildNodeSvg(prevNodeData, level, false)
            });
        }
    }
    if (nextNodeId && nodesDataset.get(nextNodeId)) {
        const nextNodeData = rawData.nodes.find(n => n.id === nextNodeId);
        if (nextNodeData) {
            updates.push({
                id: nextNodeId,
                image: buildNodeSvg(nextNodeData, level, true)
            });
        }
    }
    if (updates.length > 0) {
        nodesDataset.update(updates);
    }
}

function closeInfoPanel() {
    document.querySelector('.info-panel h3').innerHTML = `📌 정보 확인`;
    document.getElementById('sb-path').innerHTML = `노드나 화살표를 선택해주세요.`;
    document.getElementById('sb-rows').innerHTML = ``;
    document.getElementById("sidebar-content").innerHTML = ``;

    document.getElementById("infoPanel").classList.remove("open");
    document.getElementById("overlay").classList.remove("show");
    selectedEdgeId = null;
    setSelectedNodeHighlight(null);
    if (network) network.unselectAll();
}

function buildNodeSvg(node, level, isSelected = false) {
    const rows = [];
    const cols = node.columns || [];

    if (node.is_missing_target) {
        rows.push({ icon: "⚠️", name: "파일이 존재하지 않음", type: "", consts: "" });
    } else if (level >= 2) {
        for (const c of cols) {
            const isKey = c.is_pk || c.is_fk;
            if (level <= 3 && !isKey) continue;

            const isAssetCol = Boolean(c.regi_badge || (c.type && c.type.toLowerCase().startsWith("assetid")));
            let icon = isAssetCol ? "🎨" : "📄";
            if (c.is_pk && c.is_fk) icon = "🔑🔗";
            else if (c.is_pk) icon = "🔑";
            else if (c.is_fk) icon = "🔗";

            const typeStr = (level >= 3) ? `(${c.type})` : "";
            const extraConsts = (c.constraints ? [...c.constraints] : []);
            if (level === 5 && c.regi_badge && c.regi_badge.text) {
                extraConsts.push(c.regi_badge.text);
            }
            const constStr = (level === 5 && extraConsts.length > 0)
                ? `[${extraConsts.join(", ")}]` : "";

            rows.push({
                icon: icon,
                name: c.name,
                type: typeStr,
                consts: constStr,
                is_pk: c.is_pk,
                is_fk: c.is_fk
            });
        }
        if (rows.length === 0) {
            rows.push({ icon: "ℹ️", name: "(표시할 Key 컬럼 없음)", type: "", consts: "", is_empty: true });
        }
    }

    const titleText = (node.has_error ? "❌ " : "📁 ") + node.label;
    let maxChars = titleText.length * 1.15;
    for (const r of rows) {
        const lineLen = (r.icon + " " + r.name + " " + r.type + " " + r.consts).length;
        if (lineLen > maxChars) maxChars = lineLen;
    }

    const width = Math.max(200, Math.min(640, Math.ceil(maxChars * 8.5) + 36));
    const headerHeight = 38;
    const rowHeight = 24;
    const bodyHeight = rows.length > 0 ? (rows.length * rowHeight + 14) : 8;
    const height = headerHeight + bodyHeight;

    const headerBg = node.is_missing_target ? "#8B0000" : (node.has_error ? "#C9302C" : "#007ACC");
    const borderCol = isSelected ? "#FFD700" : (node.has_error ? "#FF4444" : "#3E3E42");
    const borderWidth = isSelected ? 4.5 : (node.has_error ? 3 : 2);

    let svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">`;
    svg += `<rect x="2" y="2" width="${width-4}" height="${height-4}" rx="8" ry="8" fill="#252526"/>`;
    svg += `<path d="M 2 10 Q 2 2 10 2 L ${width-10} 2 Q ${width-2} 2 ${width-2} 10 L ${width-2} ${headerHeight} L 2 ${headerHeight} Z" fill="${headerBg}"/>`;
    svg += `<rect x="2" y="2" width="${width-4}" height="${height-4}" rx="8" ry="8" fill="none" stroke="${borderCol}" stroke-width="${borderWidth}"/>`;
    svg += `<text x="14" y="24" fill="#FFFFFF" font-family="Consolas, Malgun Gothic, sans-serif" font-size="14" font-weight="bold">${escapeXml(titleText)}</text>`;

    let y = headerHeight + 22;
    for (const r of rows) {
        let nameColor = "#D4D4D4";
        if (r.is_pk) nameColor = "#FFD700";
        else if (r.is_fk) nameColor = "#00FF66";
        else if (r.is_empty) nameColor = "#888888";

        svg += `<text x="14" y="${y}" font-family="Consolas, Malgun Gothic, sans-serif" font-size="13">`;
        svg += `<tspan fill="${nameColor}" font-weight="${(r.is_pk || r.is_fk) ? "bold" : "normal"}">${escapeXml(r.icon)} ${escapeXml(r.name)}</tspan>`;
        if (r.type) {
            svg += ` <tspan fill="#569CD6">${escapeXml(r.type)}</tspan>`;
        }
        if (r.consts) {
            svg += ` <tspan fill="#CE9178" font-size="11.5">${escapeXml(r.consts)}</tspan>`;
        }
        svg += `</text>`;
        y += rowHeight;
    }

    svg += `</svg>`;
    return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

function findEdgeNearDomPos(domPos, maxRadius) {
    if (!network) return null;
    const directHit = network.getEdgeAt(domPos);
    if (directHit !== undefined && directHit !== null) {
        return directHit;
    }
    const radii = [4, 8, 12, 16, 20, 24, 28];
    const angleSteps = 12;
    for (let rIdx = 0; rIdx < radii.length; rIdx++) {
        const r = radii[rIdx];
        if (r > maxRadius) break;
        for (let a = 0; a < angleSteps; a++) {
            const rad = (a * 2 * Math.PI) / angleSteps;
            const probePos = {
                x: domPos.x + Math.cos(rad) * r,
                y: domPos.y + Math.sin(rad) * r
            };
            const nodeAtProbe = network.getNodeAt(probePos);
            if (nodeAtProbe !== undefined && nodeAtProbe !== null) continue;

            const edgeAtProbe = network.getEdgeAt(probePos);
            if (edgeAtProbe !== undefined && edgeAtProbe !== null) {
                return edgeAtProbe;
            }
        }
    }
    return null;
}

function setupDirectInputController(container) {
    const NODE_TAP_MAX_MS = 240;
    const NODE_DRAG_PIXEL_THRESHOLD = 8;

    const EDGE_TAP_MAX_MS = 800;
    const EDGE_TAP_PIXEL_THRESHOLD = 22;
    const EDGE_HIT_RADIUS = 28;

    let usingTouch = false;
    let isMultiTouch = false;
    let isPointerDown = false;
    let isDragConfirmed = false;
    let pointerDownTime = 0;
    let startDomPos = { x: 0, y: 0 };
    let lastDomPos = { x: 0, y: 0 };
    let maxMoveDistance = 0;

    let activeNodeId = null;
    let activeEdgeId = null;
    let initialNodeCanvasPos = null;
    let nodeGrabOffset = { x: 0, y: 0 };
    let holdTimer = null;

    function getDomCoords(clientX, clientY) {
        const rect = container.getBoundingClientRect();
        return {
            x: clientX - rect.left,
            y: clientY - rect.top
        };
    }

    function lockNodeForDrag(nodeId, state) {
        try {
            if (network && network.body && network.body.nodes && network.body.nodes[nodeId]) {
                network.body.nodes[nodeId].options.fixed.x = state;
                network.body.nodes[nodeId].options.fixed.y = state;
            }
        } catch (err) {}
    }

    function cancelActiveInteraction() {
        if (holdTimer) {
            clearTimeout(holdTimer);
            holdTimer = null;
        }
        if (activeNodeId !== null) {
            lockNodeForDrag(activeNodeId, false);
            network.setOptions({ interaction: { dragView: true } });
        }
        isPointerDown = false;
        isDragConfirmed = false;
        activeNodeId = null;
        activeEdgeId = null;
        initialNodeCanvasPos = null;
    }

    function onStart(clientX, clientY, rawEvent) {
        if (holdTimer) {
            clearTimeout(holdTimer);
            holdTimer = null;
        }

        const domPos = getDomCoords(clientX, clientY);
        isPointerDown = true;
        isDragConfirmed = false;
        pointerDownTime = Date.now();
        startDomPos = domPos;
        lastDomPos = domPos;
        maxMoveDistance = 0;

        const hitNode = network.getNodeAt(domPos);
        if (hitNode !== undefined && hitNode !== null) {
            activeNodeId = hitNode;
            activeEdgeId = null;

            const posMap = network.getPositions([activeNodeId]);
            const nodePos = posMap[activeNodeId] || { x: 0, y: 0 };
            initialNodeCanvasPos = { x: nodePos.x, y: nodePos.y };

            const canvasTouch = network.DOMtoCanvas(domPos);
            nodeGrabOffset = {
                x: nodePos.x - canvasTouch.x,
                y: nodePos.y - canvasTouch.y
            };

            network.setOptions({ interaction: { dragView: false } });
            lockNodeForDrag(activeNodeId, true);

            holdTimer = setTimeout(function() {
                if (isPointerDown && activeNodeId !== null) {
                    isDragConfirmed = true;
                }
            }, NODE_TAP_MAX_MS);

            if (rawEvent && rawEvent.cancelable) {
                rawEvent.preventDefault();
            }
        } else {
            activeNodeId = null;
            initialNodeCanvasPos = null;
            const hitEdge = findEdgeNearDomPos(domPos, usingTouch ? EDGE_HIT_RADIUS : 10);
            activeEdgeId = (hitEdge !== undefined && hitEdge !== null) ? hitEdge : null;
        }
    }

    function onMove(clientX, clientY, rawEvent) {
        if (!isPointerDown) return;

        const domPos = getDomCoords(clientX, clientY);
        lastDomPos = domPos;
        const dist = Math.hypot(domPos.x - startDomPos.x, domPos.y - startDomPos.y);
        if (dist > maxMoveDistance) {
            maxMoveDistance = dist;
        }

        if (maxMoveDistance >= NODE_DRAG_PIXEL_THRESHOLD) {
            isDragConfirmed = true;
        }

        if (activeNodeId !== null) {
            if (rawEvent && rawEvent.cancelable) {
                rawEvent.preventDefault();
            }
            if (isDragConfirmed) {
                const canvasPos = network.DOMtoCanvas(domPos);
                const targetX = canvasPos.x + nodeGrabOffset.x;
                const targetY = canvasPos.y + nodeGrabOffset.y;
                network.moveNode(activeNodeId, targetX, targetY);
                try {
                    if (document.getElementById("chkPhysics").checked && network.physics) {
                        network.physics.startSimulation();
                    }
                } catch (err) {}
            }
        }
    }

    function onEnd(clientX, clientY, rawEvent) {
        if (!isPointerDown) return;
        isPointerDown = false;

        if (holdTimer) {
            clearTimeout(holdTimer);
            holdTimer = null;
        }

        if (clientX !== undefined && clientY !== undefined) {
            lastDomPos = getDomCoords(clientX, clientY);
        }

        const elapsed = Date.now() - pointerDownTime;
        const wasNodeQuickTap = (!isDragConfirmed) && (maxMoveDistance < NODE_DRAG_PIXEL_THRESHOLD) && (elapsed < NODE_TAP_MAX_MS);

        if (activeNodeId !== null) {
            const targetNode = activeNodeId;
            activeNodeId = null;

            lockNodeForDrag(targetNode, false);
            network.setOptions({ interaction: { dragView: true } });

            if (wasNodeQuickTap) {
                if (rawEvent && rawEvent.cancelable) {
                    rawEvent.preventDefault();
                }
                if (initialNodeCanvasPos) {
                    network.moveNode(targetNode, initialNodeCanvasPos.x, initialNodeCanvasPos.y);
                }
                network.selectNodes([targetNode]);
                renderSidebar(targetNode);
            } else {
                try { network.storePositions(); } catch (err) {}
            }
            initialNodeCanvasPos = null;
            isDragConfirmed = false;
            return;
        }

        const wasEdgeTap = (maxMoveDistance < EDGE_TAP_PIXEL_THRESHOLD) && (elapsed < EDGE_TAP_MAX_MS);
        if (wasEdgeTap) {
            const targetEdge = activeEdgeId || findEdgeNearDomPos(lastDomPos, usingTouch ? EDGE_HIT_RADIUS : 10);
            activeEdgeId = null;
            if (targetEdge !== null && targetEdge !== undefined) {
                if (rawEvent && rawEvent.cancelable) {
                    rawEvent.preventDefault();
                }
                network.selectEdges([targetEdge]);
                renderEdgeSidebar(targetEdge);
                isDragConfirmed = false;
                return;
            }
        }
        activeEdgeId = null;

        if (maxMoveDistance < NODE_DRAG_PIXEL_THRESHOLD && elapsed < NODE_TAP_MAX_MS) {
            if (rawEvent && rawEvent.cancelable) {
                rawEvent.preventDefault();
            }
            closeInfoPanel();
        }
        isDragConfirmed = false;
    }

    container.addEventListener("contextmenu", function(e) {
        e.preventDefault();
        return false;
    });

    container.addEventListener("touchstart", function(e) {
        usingTouch = true;
        if (e.touches.length > 1) {
            isMultiTouch = true;
            cancelActiveInteraction();
            return;
        }
        isMultiTouch = false;
        const t = e.touches[0];
        onStart(t.clientX, t.clientY, e);
    }, { passive: false, capture: true });

    container.addEventListener("touchmove", function(e) {
        if (isMultiTouch || e.touches.length > 1) return;
        const t = e.touches[0];
        onMove(t.clientX, t.clientY, e);
    }, { passive: false, capture: true });

    container.addEventListener("touchend", function(e) {
        if (isMultiTouch) {
            if (e.touches.length === 0) isMultiTouch = false;
            return;
        }
        const t = (e.changedTouches && e.changedTouches[0]) ? e.changedTouches[0] : null;
        onEnd(t ? t.clientX : undefined, t ? t.clientY : undefined, e);
    }, { passive: false, capture: true });

    container.addEventListener("touchcancel", function(e) {
        cancelActiveInteraction();
    }, { passive: false, capture: true });

    container.addEventListener("mousedown", function(e) {
        if (usingTouch) return;
        if (e.button !== 0) return;
        onStart(e.clientX, e.clientY, e);
    }, true);

    window.addEventListener("mousemove", function(e) {
        if (usingTouch || !isPointerDown) return;
        onMove(e.clientX, e.clientY, e);
    }, true);

    window.addEventListener("mouseup", function(e) {
        if (usingTouch || !isPointerDown) return;
        onEnd(e.clientX, e.clientY, e);
    }, true);
}

function initGraph() {
    if (typeof vis === "undefined") {
        document.getElementById("network-container").innerHTML =
            '<div style="padding:40px;color:#FF7B88;font-size:15px;">⚠️ 그래프 엔진(vis-network)을 불러오지 못했습니다. 인터넷 연결을 확인해주세요.</div>';
        return;
    }

    nodesDataset = new vis.DataSet();
    edgesDataset = new vis.DataSet();

    const datalist = document.getElementById("tableList");
    rawData.nodes.forEach(n => {
        const opt = document.createElement("option");
        opt.value = n.id;
        datalist.appendChild(opt);
    });

    const container = document.getElementById("network-container");
    const data = { nodes: nodesDataset, edges: edgesDataset };
    
    const options = {
        nodes: {
            shape: "image",
            shapeProperties: { useImageSize: true },
            chosen: false
        },
        edges: {
            arrows: { to: { enabled: true, scaleFactor: 1.0 } },
            selectionWidth: 4,
            smooth: { enabled: true, type: "dynamic" }
        },
        physics: {
            enabled: true,
            solver: "forceAtlas2Based",
            forceAtlas2Based: {
                gravitationalConstant: -180,
                centralGravity: 0.01,
                springLength: 260,
                springConstant: 0.05,
                avoidOverlap: 1.0
            },
            stabilization: { iterations: 150 }
        },
        interaction: {
            dragNodes: false,
            dragView: true,
            zoomView: true,
            hover: false,
            selectConnectedEdges: false,
            navigationButtons: false,
            keyboard: true
        }
    };

    network = new vis.Network(container, data, options);
    updateGraphLevel();
    setupDirectInputController(container);
    updateSummaryStats();
}

function updateSummaryStats() {
    const totalTables = rawData.nodes.filter(n => !n.is_missing_target).length;
    const totalFks = rawData.edges.length;
    const brokenFks = rawData.edges.filter(e => !e.is_valid).length;
    document.getElementById("stats-info").innerText =
        `테이블: ${totalTables}개 | 참조(FK) 연결: ${totalFks}개 (위반: ${brokenFks}건) | 갱신: ${rawData.generated_at}`;
}

function updateGraphLevel() {
    if (!nodesDataset || !edgesDataset) return;
    const level = parseInt(document.getElementById("levelSelect").value, 10);
    const hideIsolated = document.getElementById("chkHideIsolated").checked;

    const updatedNodes = [];
    for (const n of rawData.nodes) {
        if (hideIsolated && n.is_isolated) continue;
        updatedNodes.push({
            id: n.id,
            image: buildNodeSvg(n, level, n.id === selectedNodeId),
            title: undefined 
        });
    }

    const currentIds = new Set(updatedNodes.map(n => n.id));
    const existingIds = nodesDataset.getIds();
    const toRemove = existingIds.filter(id => !currentIds.has(id));
    if (toRemove.length > 0) nodesDataset.remove(toRemove);
    nodesDataset.update(updatedNodes);

    const pairCounts = {};
    const pairIndex = {};
    for (const e of rawData.edges) {
        if (!currentIds.has(e.from) || !currentIds.has(e.to)) continue;
        const key = [e.from, e.to].sort().join("::");
        pairCounts[key] = (pairCounts[key] || 0) + 1;
    }

    const updatedEdges = [];
    for (const e of rawData.edges) {
        if (!currentIds.has(e.from) || !currentIds.has(e.to)) continue;

        const key = [e.from, e.to].sort().join("::");
        const totalInPair = pairCounts[key] || 1;
        const idxInPair = pairIndex[key] || 0;
        pairIndex[key] = idxInPair + 1;

        let smoothOpt = { enabled: true, type: "cubicBezier", forceDirection: "none", roundness: 0.25 };
        if (totalInPair > 1) {
            const dirType = (idxInPair % 2 === 0) ? "curvedCW" : "curvedCCW";
            const roundVal = 0.2 + Math.floor(idxInPair / 2) * 0.18;
            smoothOpt = { enabled: true, type: dirType, roundness: roundVal };
        }

        updatedEdges.push({
            id: e.id,
            from: e.from,
            to: e.to,
            label: undefined,
            smooth: smoothOpt,
            color: {
                color: e.is_valid ? "#00E5FF" : "#FF4444",
                highlight: e.is_valid ? "#FFD700" : "#FF7777",
                hover: e.is_valid ? "#66F0FF" : "#FF7777"
            },
            dashes: !e.is_valid,
            width: e.is_valid ? 2.5 : 3.5
        });
    }

    // 💡 edgesDataset.clear() 대신 부분 업데이트를 사용하여 선택 상태 증발 방지
    const currentEdgeIds = new Set(updatedEdges.map(e => e.id));
    const existingEdgeIds = edgesDataset.getIds();
    const edgesToRemove = existingEdgeIds.filter(id => !currentEdgeIds.has(id));
    if (edgesToRemove.length > 0) edgesDataset.remove(edgesToRemove);
    edgesDataset.update(updatedEdges);

    // 💡 표시 단계 변경 후에도 참조 화살표(또는 테이블) 하이라이트 선택 상태를 그대로 복원
    if (network) {
        if (selectedEdgeId) {
            if (edgesDataset.get(selectedEdgeId)) {
                network.selectEdges([selectedEdgeId]);
            } else {
                closeInfoPanel();
            }
        } else if (selectedNodeId) {
            if (nodesDataset.get(selectedNodeId)) {
                network.selectNodes([selectedNodeId]);
            } else {
                closeInfoPanel();
            }
        }
    }
    
    if (window.innerWidth <= 900) {
        document.getElementById("optionsPanel").classList.remove("show");
    }
}

function renderSidebar(nodeId) {
    const node = rawData.nodes.find(n => n.id === nodeId);
    if (!node) return;

    selectedEdgeId = null;
    setSelectedNodeHighlight(nodeId);

    document.querySelector('.info-panel h3').innerHTML = `📌 ${escapeXml(node.label)}`;
    document.getElementById('sb-path').innerHTML = `상대 경로: ${escapeXml(node.rel_path)}`;
    document.getElementById('sb-rows').innerHTML = `데이터: ${node.row_count}행`;

    const container = document.getElementById("sidebar-content");
    let html = "";

    if (node.errors && node.errors.length > 0) {
        html += `<div class="section-title">🛡️ 무결성 위반 사항</div>`;
        for (const err of node.errors) {
            html += `<div class="err-box">❌ ${escapeXml(err)}</div>`;
        }
    } else {
        html += `<div class="section-title">🛡️ 무결성 검증 상태</div>`;
        html += `<div class="ok-box">✅ 무결성 위반 사항이 없습니다.</div>`;
    }

    html += `<div class="section-title">📋 전체 컬럼 스키마 (${node.columns.length}개)</div>`;
    if (node.columns.length > 0) {
        html += `<table class="col-table"><thead><tr><th>구분</th><th>컬럼명</th><th>타입 / 제약조건</th></tr></thead><tbody>`;
        for (const c of node.columns) {
            const isAssetCol = Boolean(c.regi_badge || (c.type && c.type.toLowerCase().startsWith("assetid")));
            let keyBadge = "";
            if (c.is_pk) keyBadge += `<span class="badge-pk">🔑PK</span><br>`;
            if (c.is_fk) keyBadge += `<span class="badge-fk">🔗FK</span><br>`;
            if (isAssetCol) keyBadge += `<span style="color:#00E5FF;font-weight:bold;white-space:nowrap;">🎨Asset</span><br>`;
            if (!keyBadge) keyBadge = `<span style="color:#777;">일반</span>`;

            let constHtml = "";
            if (c.constraints && c.constraints.length > 0) {
                constHtml += `<span class="badge-const">${escapeXml(c.constraints.join(" / "))}</span>`;
            }
            if (c.fk_Targets && c.fk_Targets.length > 0) {
                constHtml += `<span class="badge-const" style="color:#00FF66;">참조: ${escapeXml(c.fk_Targets.join(", "))}</span>`;
            }
            if (c.regi_badge && c.regi_badge.text) {
                let rColor = "#00E5FF";
                let rIcon = "🎨";
                if (c.regi_badge.status === "outdated") {
                    rColor = "#FFD700";
                    rIcon = "⚠️";
                } else if (c.regi_badge.status === "unbound" || c.regi_badge.status === "error") {
                    rColor = "#FF5555";
                    rIcon = "❌";
                }
                constHtml += `<span class="badge-const" style="color:${rColor};font-weight:bold;">${rIcon} ${escapeXml(c.regi_badge.text)}</span>`;
            }

            html += `<tr>
                <td style="text-align:center;">${keyBadge}</td>
                <td style="font-weight:bold;color:#FFF;">${escapeXml(c.name)}</td>
                <td><span class="badge-type">${escapeXml(c.type)}</span>${constHtml}</td>
            </tr>`;
        }
        html += `</tbody></table><br><br>`;
    } else {
        html += `<div class="meta-badge">컬럼 정보가 없습니다.</div>`;
    }

    container.innerHTML = html;
    
    panelOpenedAt = Date.now();
    document.getElementById("infoPanel").classList.add("open");
    if (window.innerWidth <= 900) {
        document.getElementById("overlay").classList.add("show");
    }
}

function renderEdgeSidebar(edgeId) {
    const edge = rawData.edges.find(e => e.id === edgeId);
    if (!edge) return;

    // 💡 현재 선택된 화살표 ID를 저장하고 테이블 테두리 하이라이트 해제
    selectedEdgeId = edgeId;
    setSelectedNodeHighlight(null);

    document.querySelector('.info-panel h3').innerHTML = `🔗 참조 무결성 연결 (FK)`;
    document.getElementById('sb-path').innerHTML = `<span style="color:#00E5FF;">${escapeXml(edge.from)}</span> ➔ <span style="color:#FFD700;">${escapeXml(edge.to)}</span>`;
    document.getElementById('sb-rows').innerHTML = `외래키 객체명: <b>[${escapeXml(edge.fk_name)}]</b>`;

    const container = document.getElementById("sidebar-content");
    let html = "";

    if (edge.is_valid) {
        html += `<div class="section-title">🛡️ 검증 상태</div>`;
        html += `<div class="ok-box">✅ 정상적인 참조(FK) 연결입니다.</div>`;
    } else {
        html += `<div class="section-title">🛡️ 무결성 위반 사항</div>`;
        html += `<div class="err-box">❌ ${escapeXml(edge.error_msg)}</div>`;
    }

    html += `<div class="section-title">📋 매핑 상세정보</div>`;
    html += `<table class="col-table"><thead><tr>
                <th>로컬 컬럼<br><span style="font-size:10px;font-weight:normal;color:#AAA;">(${escapeXml(edge.from)})</span></th>
                <th>타겟 PK<br><span style="font-size:10px;font-weight:normal;color:#AAA;">(${escapeXml(edge.to)})</span></th>
             </tr></thead><tbody>`;
    
    const maxLen = Math.max(edge.local_cols.length, edge.target_cols.length);
    for(let i=0; i<maxLen; i++) {
        const lCol = edge.local_cols[i] || "? (누락)";
        const tCol = edge.target_cols[i] || "? (누락)";
        html += `<tr>
            <td style="font-weight:bold;color:#00FF66;">${escapeXml(lCol)}</td>
            <td style="font-weight:bold;color:#FFD700;">${escapeXml(tCol)}</td>
        </tr>`;
    }
    html += `</tbody></table><br><br>`;

    container.innerHTML = html;
    
    panelOpenedAt = Date.now();
    document.getElementById("infoPanel").classList.add("open");
    if (window.innerWidth <= 900) {
        document.getElementById("overlay").classList.add("show");
    }
}

function onSearchTable() {
    const val = document.getElementById("searchInput").value.trim();
    if (!val) return;
    const found = rawData.nodes.find(n => n.id.toLowerCase() === val.toLowerCase());
    if (found && nodesDataset.get(found.id)) {
        network.selectNodes([found.id]);
        network.focus(found.id, { scale: 1.15, animation: { duration: 400, easingFunction: "easeInOutQuad" } });
        renderSidebar(found.id);
        
        if (window.innerWidth <= 900) {
            document.getElementById("optionsPanel").classList.remove("show");
        }
    }
}

function togglePhysics() {
    const enabled = document.getElementById("chkPhysics").checked;
    network.setOptions({ physics: { enabled: enabled } });
}

function fitNetwork() {
    network.fit({ animation: { duration: 400, easingFunction: "easeInOutQuad" } });
    if (window.innerWidth <= 900) {
        document.getElementById("optionsPanel").classList.remove("show");
    }
}

window.addEventListener("DOMContentLoaded", initGraph);
</script>
</body>
</html>
"""

def generate_erd_html(workspace_root, project_name, df_dict, file_errors, fk_edges, output_path):
    nodes_data = []
    edges_data = []
    
    connected_tables = set()
    for edge in fk_edges:
        connected_tables.add(edge['from'])
        connected_tables.add(edge['to'])

    existing_tables = set(df_dict.keys())
    missing_targets = set()

    for t_name, t_data in sorted(df_dict.items()):
        meta = t_data['meta']
        info = t_data['info']
        df = t_data['df']
        rel_path = t_data.get('rel_path', t_name)
        
        pks = meta.get('primaryKey', [])
        fks = meta.get('foreignKeys', {})
        
        fk_col_map = {}
        for fk_name, fk_info in fks.items():
            target_t = os.path.basename(fk_info.get('targetTable', ''))
            for c in fk_info.get('columns', []):
                if c not in fk_col_map:
                    fk_col_map[c] = []
                fk_col_map[c].append(f"{fk_name} ➔ {target_t}")

        columns_list = []
        for col_name, col_meta in info.items():
            is_pk = col_name in pks
            is_fk = col_name in fk_col_map
            c_type = col_meta.get('type', '') or 'untyped'
            constraints = col_meta.get('constraints', [])
            columns_list.append({
                'name': col_name,
                'type': c_type,
                'constraints': constraints,
                'is_pk': is_pk,
                'is_fk': is_fk,
                'fk_Targets': fk_col_map.get(col_name, []),
                'regi_badge': col_meta.get('regi_badge', None),
                'is_schema': col_meta.get('is_schema', False)
            })

        errs = file_errors.get(t_name, [])
        nodes_data.append({
            'id': t_name,
            'label': t_name,
            'rel_path': rel_path,
            'row_count': len(df),
            'columns': columns_list,
            'errors': errs,
            'has_error': len(errs) > 0,
            'is_isolated': t_name not in connected_tables,
            'is_missing_target': False
        })

    for edge in fk_edges:
        target_id = edge['to']
        if target_id not in existing_tables and target_id not in missing_targets:
            missing_targets.add(target_id)
            nodes_data.append({
                'id': target_id,
                'label': target_id,
                'rel_path': '❌ 파일 없음 (Missing Target)',
                'row_count': 0,
                'columns': [],
                'errors': [f"외래키 '{edge['fk_name']}'가 참조하지만 워크스페이스 내에 존재하지 않는 테이블입니다."],
                'has_error': True,
                'is_isolated': False,
                'is_missing_target': True
            })

    for idx, edge in enumerate(fk_edges):
        edges_data.append({
            'id': f"edge_{idx}",
            'from': edge['from'],
            'to': edge['to'],
            'fk_name': edge['fk_name'],
            'local_cols': edge['local_cols'],
            'target_cols': edge['target_cols'],
            'is_valid': edge['is_valid'],
            'error_msg': edge.get('error_msg', '')
        })

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    graph_json = json.dumps({
        'project_name': project_name,
        'workspace_root': workspace_root,
        'generated_at': now_str,
        'nodes': nodes_data,
        'edges': edges_data
    }, ensure_ascii=False)

    html_content = (
        HTML_TEMPLATE
        .replace("__PROJECT_NAME__", str(project_name))
        .replace("__GENERATED_AT__", now_str)
        .replace("__GRAPH_JSON__", graph_json)
    )

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    return True
