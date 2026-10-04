(function () {
    const routes = JSON.parse(document.getElementById("atlas-routes").textContent);
    const pagesByFile = {
        "index.html": "dashboard",
        "workspace.html": "workspace",
        "jobs.html": "jobs",
        "review.html": "review",
        "job.html": "job",
        "applications.html": "applications",
        "application.html": "application",
        "interviews.html": "interviews",
        "workflows.html": "workflows",
        "settings.html": "settings"
    };
    const app = document.getElementById("app");

    function rewriteLinks(node) {
        if (node.nodeType !== Node.ELEMENT_NODE) return;

        const links = [];
        if (node.matches("a[href]")) links.push(node);
        links.push(...node.querySelectorAll("a[href]"));

        links.forEach(link => {
            const current = new URL(link.getAttribute("href"), window.location.href);
            const page = pagesByFile[current.pathname.split("/").pop()];
            if (!page) return;

            const target = new URL(routes[page], window.location.origin);
            target.search = current.search;
            target.hash = current.hash;
            link.href = `${target.pathname}${target.search}${target.hash}`;
        });
    }

    rewriteLinks(app);
    new MutationObserver(records => {
        records.forEach(record => record.addedNodes.forEach(rewriteLinks));
    }).observe(app, { childList: true, subtree: true });
})();