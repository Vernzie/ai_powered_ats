const page=document.body.dataset.page;
const nav=[
["dashboard","index.html","▦","Dashboard",""],
["jobs","jobs.html","▤","Jobs","8"],
["applications","applications.html","◫","Applications",""],
["interviews","interviews.html","□","Interviews","5"],
["workflows","workflows.html","⇄","Workflows",""],
["settings","settings.html","⚙","Settings",""]
];
document.getElementById("app").innerHTML=`
<div class="shell"><aside class="sidebar">
<div class="brand"><div class="brandmark">A</div><div><strong>ATLAS ATS</strong><small>Recruitment workspace</small></div></div>
<nav class="nav"><div class="navlabel">Workspace</div>${nav.slice(0,4).map(n=>`<a class="navitem ${page===n[0]?"active":""}" href="${n[1]}"><span>${n[2]}</span>${n[3]} ${n[4]?`<b>${n[4]}</b>`:""}</a>`).join("")}
<div class="navlabel">System</div>${nav.slice(4).map(n=>`<a class="navitem ${page===n[0]?"active":""}" href="${n[1]}"><span>${n[2]}</span>${n[3]}</a>`).join("")}</nav>
<div class="sidebarfoot"><div class="status"><i></i> All systems operational</div><div class="miniuser"><div class="avatar">VL</div><div><strong>Vern Link</strong><small>Administrator</small></div></div></div>
</aside><main class="main"><header class="topbar"><div class="crumb"><a href="index.html">Workspace</a><b>/</b>${page[0].toUpperCase()+page.slice(1)}</div><div class="topright"><label class="search">⌕ <input placeholder="Search jobs, candidates..."></label><button class="bell">♢</button><div class="avatar">VL</div></div></header><div id="pageContent" class="content"></div></main></div>`;
