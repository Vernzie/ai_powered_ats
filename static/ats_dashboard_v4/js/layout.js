const page=document.body.dataset.page;
const storedSidebarCollapsed=localStorage.getItem("atlasSidebarCollapsed");
const sidebarStartsCollapsed=storedSidebarCollapsed===null?window.matchMedia("(max-width: 700px)").matches:storedSidebarCollapsed==="true";
const sidebarCounts=JSON.parse(document.getElementById("sidebar-counts")?.textContent||"{}");
const nav=[
["dashboard","index.html","▦","Overview",""],
["jobs","jobs.html","▤","Jobs",String(sidebarCounts.jobs??0)],
["applications","applications.html","◫","Applications",String(sidebarCounts.applications??0)],
["interviews","interviews.html","□","Interviews",String(sidebarCounts.interviews??0)],
["workspace","workspace.html","▣","Workspace",""]
];
document.getElementById("app").innerHTML=`
<style>
.sidebar{z-index:15;transition:transform .65s cubic-bezier(.22,1,.36,1)}
.main{transition:margin-left .65s cubic-bezier(.22,1,.36,1),width .65s cubic-bezier(.22,1,.36,1)}
.shell.sidebar-collapsed .sidebar{transform:translateX(-100%)}
.shell.sidebar-collapsed .main{margin-left:0;width:100%}
.global-sidebar-toggle{position:fixed;z-index:20;left:235px;top:50%;transform:translate(-50%,-50%);width:28px;height:34px;border:1px solid #cbd8ff;background:#fff;color:var(--blue);display:grid;place-items:center;cursor:pointer;box-shadow:0 2px 8px #142d581c;transition:left .65s cubic-bezier(.22,1,.36,1),transform .65s cubic-bezier(.22,1,.36,1),background .15s ease}
.global-sidebar-toggle::before{content:"";width:7px;height:7px;border-top:2px solid currentColor;border-right:2px solid currentColor;transform:rotate(135deg)}
.global-sidebar-toggle.is-collapsed{left:0;transform:translateY(-50%)}
.global-sidebar-toggle.is-collapsed::before{transform:rotate(45deg)}
.global-sidebar-toggle:hover{background:#edf2ff}
.navlabel.workspace-navlabel{margin-top:14px;border-top:1px solid #ffffff40;padding-top:18px}
@media(max-width:1000px){.global-sidebar-toggle{left:190px}}
@media(max-width:700px){.sidebar{display:flex;width:min(235px,85vw);transform:translateX(-100%)}.shell:not(.sidebar-collapsed) .sidebar{transform:translateX(0);box-shadow:8px 0 28px #10131730}.main,.shell.sidebar-collapsed .main{margin-left:0;width:100%}.global-sidebar-toggle,.global-sidebar-toggle.is-collapsed{left:0;top:96px;transform:translateY(-50%)}.shell:not(.sidebar-collapsed) .global-sidebar-toggle{left:min(235px,85vw);transform:translate(-50%,-50%)}}
@media(prefers-reduced-motion:reduce){.sidebar,.main,.global-sidebar-toggle{transition:none}}
</style>
<div class="shell ${sidebarStartsCollapsed?"sidebar-collapsed":""}"><aside class="sidebar">
<div class="brand"><div class="brandmark" role="img" aria-label="Telikom logo">T</div><div><strong>Telikom ATS</strong><small>Recruitment workspace</small></div></div>
<nav class="nav"><div class="navlabel">Hiring</div>${nav.slice(0,4).map(n=>`<a class="navitem ${page===n[0]||(page==="job-create"&&n[0]==="jobs")?"active":""}" href="${n[1]}"><span>${n[2]}</span>${n[3]} ${n[4]?`<b>${n[4]}</b>`:""}</a>`).join("")}
<div class="navlabel workspace-navlabel">Workspace</div>${nav.slice(4).map(n=>`<a class="navitem ${page===n[0]?"active":""}" href="${n[1]}"><span>${n[2]}</span>${n[3]}</a>`).join("")}</nav>
<div class="sidebarfoot"><div class="status"><i></i> All systems operational</div><div class="miniuser"><div class="avatar">VL</div><div><strong>Vern Link</strong><small>Administrator</small></div></div></div>
</aside><button type="button" id="global-sidebar-toggle" class="global-sidebar-toggle ${sidebarStartsCollapsed?"is-collapsed":""}" aria-label="${sidebarStartsCollapsed?"Expand":"Collapse"} dashboard sidebar" aria-expanded="${!sidebarStartsCollapsed}" title="${sidebarStartsCollapsed?"Expand":"Collapse"} dashboard sidebar"></button><main class="main"><header class="topbar"><div class="crumb"><a href="index.html">Workspace</a><b>/</b>${page==="job-create"?"Create job":page[0].toUpperCase()+page.slice(1)}</div><div class="topright"><label class="search">⌕ <input placeholder="Search jobs, candidates..."></label><button class="bell">♢</button><div class="avatar">VL</div></div></header><div id="pageContent" class="content"></div></main></div>`;

const globalSidebarToggle=document.getElementById("global-sidebar-toggle");
globalSidebarToggle.addEventListener("click",()=>{
	const shell=document.querySelector(".shell");
	const collapsed=shell.classList.toggle("sidebar-collapsed");
	globalSidebarToggle.classList.toggle("is-collapsed",collapsed);
	globalSidebarToggle.setAttribute("aria-expanded",String(!collapsed));
	globalSidebarToggle.setAttribute("aria-label",`${collapsed?"Expand":"Collapse"} dashboard sidebar`);
	globalSidebarToggle.title=`${collapsed?"Expand":"Collapse"} dashboard sidebar`;
	localStorage.setItem("atlasSidebarCollapsed",String(collapsed));
});
