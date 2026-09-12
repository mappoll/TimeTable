function setupControls() {
    const sheet = document.getElementById("control-sheet");
    const menu = document.getElementById("menu-button");
    const form = document.getElementById("search-form");
    const hasDiagram = document.body.dataset.hasDiagram === "true";
    const storageKey = "timetable.search.v2";
    const directions = ["outbound", "return"];
    const validTime = value => typeof value === "string" && /^([01]\d|2[0-3]):[0-5]\d$/.test(value);
    function readSettings() {
        let saved = {};
        try {
            const current = localStorage.getItem(storageKey);
            if (current !== null) {
                saved = JSON.parse(current);
            } else {
                const legacy = JSON.parse(localStorage.getItem("timetable.search"));
                if (legacy && directions.includes(legacy.direction) && validTime(legacy.target_time)) {
                    saved = { [legacy.direction]: {target_time: legacy.target_time}, active_direction: legacy.direction };
                    localStorage.setItem(storageKey, JSON.stringify(saved));
                }
            }
        } catch (_) { /* 保存できない場合も手動検索を利用できる。 */ }
        const clean = {};
        for (const direction of directions) {
            if (validTime(saved?.[direction]?.target_time)) {
                clean[direction] = {target_time: saved[direction].target_time};
            }
        }
        if (directions.includes(saved?.active_direction)) clean.active_direction = saved.active_direction;
        return clean;
    }
    let settings = readSettings();
    function restoreDirection(direction) {
        form.elements.direction.value = direction;
        const time = settings[direction]?.target_time;
        form.elements.target_time.value = time || "";
        if (time) form.requestSubmit();
    }
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
    for (const input of form.querySelectorAll('input[name="direction"]')) {
        input.addEventListener("change", () => {
            settings = readSettings();
            restoreDirection(input.value);
        });
    }
    if (document.body.dataset.requestMethod === "POST") {
        if (hasDiagram) {
            try {
                const direction = form.elements.direction.value;
                settings[direction] = {target_time: form.elements.target_time.value};
                settings.active_direction = direction;
                localStorage.setItem(storageKey, JSON.stringify(settings));
            } catch (_) { /* 保存できない環境でも検索は利用できる。 */ }
        } else openSheet();
        return;
    }
    if (settings[settings.active_direction]?.target_time) {
        restoreDirection(settings.active_direction);
    } else openSheet();
}
