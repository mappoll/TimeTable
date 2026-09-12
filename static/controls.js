function setupControls() {
    const sheet = document.getElementById("control-sheet");
    const menu = document.getElementById("menu-button");
    const form = document.getElementById("search-form");
    const hasDiagram = document.body.dataset.hasDiagram === "true";
    const storageKey = "timetable.search";
    function openSheet() {
        if (!sheet.open) sheet.showModal();
        menu.setAttribute("aria-expanded", "true");
        document.getElementById("close-sheet").focus();
    }
    menu.addEventListener("click", openSheet);
    document.getElementById("close-sheet").addEventListener("click", () => sheet.close());
    sheet.addEventListener("close", () => { menu.setAttribute("aria-expanded", "false"); menu.focus(); });
    sheet.addEventListener("click", event => {
        if (event.target !== sheet) return;
        const bounds = sheet.getBoundingClientRect();
        if (event.clientY < bounds.top || event.clientX < bounds.left || event.clientX > bounds.right || event.clientY > bounds.bottom) sheet.close();
    });
    if (document.body.dataset.requestMethod === "POST") {
        if (hasDiagram) {
            try {
                localStorage.setItem(storageKey, JSON.stringify({
                    direction: form.elements.direction.value,
                    target_time: form.elements.target_time.value
                }));
            } catch (_) { /* 保存できない環境でも検索は利用できる。 */ }
        } else openSheet();
        return;
    }
    let saved;
    try { saved = JSON.parse(localStorage.getItem(storageKey)); } catch (_) { /* 初回扱い */ }
    if (saved && ["outbound", "return"].includes(saved.direction)
        && typeof saved.target_time === "string"
        && /^([01]\d|2[0-3]):[0-5]\d$/.test(saved.target_time)) {
        form.elements.direction.value = saved.direction;
        form.elements.target_time.value = saved.target_time;
        form.requestSubmit();
    } else openSheet();
}
