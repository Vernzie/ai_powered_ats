(() => {
    const shell = document.querySelector('.shell');
    const sidebar = document.getElementById('dashboard-sidebar');
    const toggle = document.getElementById('review-sidebar-toggle');
    if (!shell || !sidebar || !toggle) return;

    toggle.addEventListener('click', () => {
        const expanded = shell.classList.toggle('sidebar-collapsed') === false;
        toggle.classList.toggle('is-collapsed', !expanded);
        toggle.setAttribute('aria-expanded', String(expanded));
        toggle.setAttribute('aria-label', `${expanded ? 'Collapse' : 'Expand'} dashboard sidebar`);
        toggle.title = `${expanded ? 'Collapse' : 'Expand'} dashboard sidebar`;
    });
})();