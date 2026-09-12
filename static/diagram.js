

        document.addEventListener(
            "DOMContentLoaded",
            function () {

                setupControls();

                const svg =
                    document.getElementById(
                        "timetable-diagram"
                    );


                if (!svg) {
                    return;
                }


                /* =============================================
                   ズーム関連
                   ============================================= */

                const zoomLabel =
                    document.getElementById(
                        "zoom-label"
                    );

                const zoomInButton =
                    document.getElementById(
                        "zoom-in"
                    );

                const zoomOutButton =
                    document.getElementById(
                        "zoom-out"
                    );

                const zoomResetButton =
                    document.getElementById(
                        "zoom-reset"
                    );


                const leftMargin = 64;


                const diagramWidth =
                    Number(
                        svg.dataset.diagramWidth
                    );


                const topMargin =
                    Number(
                        svg.dataset.topMargin
                    );


                const stationSpacing =
                    Number(
                        svg.dataset.stationSpacing
                    );


                const stationCount =
                    Number(
                        svg.dataset.stationCount
                    );


                let zoom = 1.0;

                const minZoom = 1.0;
                const maxZoom = 3.0;
                const zoomStep = 0.25;


                /* ピンチ操作 */
                let pinchStartDistance = null;
                let pinchStartZoom = 1.0;
                let suppressClickUntil = 0;



                function scaleX(baseX) {

                    return (
                        leftMargin
                        + (baseX - leftMargin)
                        * zoom
                    );
                }



                function scaleY(baseY) {

                    return (
                        topMargin
                        + (baseY - topMargin)
                        * zoom
                    );
                }



                function updateDiagram() {

                    const newWidth =
                        104
                        + diagramWidth
                        * zoom;


                    const newHeight =
                        (topMargin * 2)
                        + (
                            (stationCount - 1)
                            * stationSpacing
                            * zoom
                        );


                    svg.setAttribute(
                        "width",
                        newWidth
                    );


                    svg.setAttribute(
                        "height",
                        newHeight
                    );


                    svg.setAttribute(
                        "viewBox",
                        `0 0 ${newWidth} ${newHeight}`
                    );


                    /* 時間線 */
                    svg.querySelectorAll(
                        ".diagram-time-grid"
                    ).forEach(
                        function (line) {

                            const x =
                                scaleX(
                                    Number(
                                        line.dataset.baseX
                                    )
                                );

                            line.setAttribute(
                                "x1",
                                x
                            );

                            line.setAttribute(
                                "x2",
                                x
                            );

                            line.setAttribute(
                                "y2",
                                newHeight - 20
                            );
                        }
                    );


                    /* 時刻表示 */
                    svg.querySelectorAll(
                        ".diagram-time-label"
                    ).forEach(
                        function (text) {

                            const x =
                                scaleX(
                                    Number(
                                        text.dataset.baseX
                                    )
                                );

                            text.setAttribute(
                                "x",
                                x
                            );
                        }
                    );


                    /* 駅線 */
                    svg.querySelectorAll(
                        ".diagram-station-line"
                    ).forEach(
                        function (line) {

                            const y =
                                scaleY(
                                    Number(
                                        line.dataset.baseY
                                    )
                                );

                            line.setAttribute(
                                "y1",
                                y
                            );

                            line.setAttribute(
                                "y2",
                                y
                            );

                            line.setAttribute(
                                "x2",
                                leftMargin
                                + diagramWidth
                                * zoom
                            );
                        }
                    );


                    /* 駅名 */
                    svg.querySelectorAll(
                        ".diagram-station-name"
                    ).forEach(
                        function (text) {

                            const y =
                                scaleY(
                                    Number(
                                        text.dataset.baseY
                                    )
                                );

                            text.setAttribute(
                                "y",
                                y + 4
                            );
                        }
                    );


                    /* 希望時刻線 */
                    const targetLine =
                        svg.querySelector(
                            ".diagram-target-line"
                        );


                    if (targetLine) {

                        const x =
                            scaleX(
                                Number(
                                    targetLine.dataset.baseX
                                )
                            );

                        targetLine.setAttribute(
                            "x1",
                            x
                        );

                        targetLine.setAttribute(
                            "x2",
                            x
                        );

                        targetLine.setAttribute(
                            "y2",
                            newHeight - 20
                        );
                    }


                    const targetLabel =
                        svg.querySelector(
                            ".diagram-target-label"
                        );


                    if (targetLabel) {

                        const x =
                            scaleX(
                                Number(
                                    targetLabel.dataset.baseX
                                )
                            );

                        targetLabel.setAttribute(
                            "x",
                            x
                        );
                    }


                    /* 列車線 */
                    svg.querySelectorAll(
                        ".diagram-train-line"
                    ).forEach(
                        function (line) {

                            const basePoints =
                                line
                                    .dataset
                                    .basePoints
                                    .trim()
                                    .split(/\s+/);


                            const newPoints =
                                basePoints.map(
                                    function (point) {

                                        const parts =
                                            point.split(",");

                                        const baseX =
                                            Number(parts[0]);

                                        const baseY =
                                            Number(parts[1]);

                                        return (
                                            scaleX(baseX)
                                            + ","
                                            + scaleY(baseY)
                                        );
                                    }
                                );


                            line.setAttribute(
                                "points",
                                newPoints.join(" ")
                            );
                        }
                    );


                    /* 駅ボックス */
                    svg.querySelectorAll(
                        ".diagram-stop-box"
                    ).forEach(
                        function (box) {

                            const baseX =
                                Number(
                                    box.dataset.baseX
                                );

                            const baseY =
                                Number(
                                    box.dataset.baseY
                                );

                            const offsetY =
                                Number(
                                    box.dataset.offsetY || 0
                                );


                            const x =
                                scaleX(baseX);

                            const y =
                                scaleY(baseY)
                                + offsetY;


                            box.setAttribute(
                                "transform",
                                `translate(${x} ${y})`
                            );
                        }
                    );


                    zoomLabel.textContent =
                        Math.round(
                            zoom * 100
                        )
                        + "%";
                    updateTransferLine();
                    syncAxes();
                }



                zoomInButton.addEventListener(
                    "click",
                    function () {

                        if (zoom < maxZoom) {

                            zoom = Math.min(maxZoom, zoom + zoomStep);

                            updateDiagram();
                        }
                    }
                );



                zoomOutButton.addEventListener(
                    "click",
                    function () {

                        if (zoom > minZoom) {

                            zoom = Math.max(minZoom, zoom - zoomStep);

                            updateDiagram();
                        }
                    }
                );



                zoomResetButton.addEventListener(
                    "click",
                    function () {

                        zoom = 1.0;

                        updateDiagram();
                    }
                );



                /* =============================================
                   ピンチズーム
                   ============================================= */

                svg.addEventListener("touchcancel", function () { pinchStartDistance = null; });

                function getTouchDistance(
                    touch1,
                    touch2
                ) {

                    const dx =
                        touch2.clientX
                        - touch1.clientX;

                    const dy =
                        touch2.clientY
                        - touch1.clientY;


                    return Math.sqrt(
                        dx * dx
                        + dy * dy
                    );
                }



                svg.addEventListener(
                    "touchstart",
                    function (event) {

                        if (
                            event.touches.length
                            !== 2
                        ) {
                            return;
                        }


                        event.preventDefault();
                        suppressClickUntil = Date.now() + 500;
                        pinchStartDistance =
                            getTouchDistance(
                                event.touches[0],
                                event.touches[1]
                            );


                        pinchStartZoom =
                            zoom;
                    },
                    {
                        passive: false
                    }
                );



                svg.addEventListener(
                    "touchmove",
                    function (event) {

                        if (
                            event.touches.length
                            !== 2
                            ||
                            pinchStartDistance
                            === null
                        ) {
                            return;
                        }


                        event.preventDefault();
                        suppressClickUntil = Date.now() + 500;


                        const currentDistance =
                            getTouchDistance(
                                event.touches[0],
                                event.touches[1]
                            );


                        const scale =
                            currentDistance
                            / pinchStartDistance;


                        zoom =
                            pinchStartZoom
                            * scale;


                        if (zoom < minZoom) {
                            zoom = minZoom;
                        }


                        if (zoom > maxZoom) {
                            zoom = maxZoom;
                        }


                        updateDiagram();
                    },
                    {
                        passive: false
                    }
                );



                svg.addEventListener(
                    "touchend",
                    function (event) {

                        if (
                            event.touches.length
                            < 2
                        ) {
                            pinchStartDistance =
                                null;
                        }
                    }
                );



                /* =============================================
                   乗車中の列車選択
                   ============================================= */

                let selectedTrainIndex = null;
                let transferSourceBox = null;
                let transferTargetBox = null;
                const transferLine = document.getElementById("transfer-line");

                function updateSelection() {
                    svg.querySelectorAll("[data-train-index]").forEach(function (element) {
                        const selected = element.dataset.trainIndex === selectedTrainIndex;
                        const candidate = transferTargetBox !== null
                            && element.dataset.trainIndex === transferTargetBox.dataset.trainIndex;
                        element.classList.toggle("is-selected", selected);
                        element.classList.toggle("is-transfer", candidate);
                        element.classList.toggle("is-dimmed",
                            selectedTrainIndex !== null && !selected && !candidate);
                        element.classList.toggle("is-transfer-stop",
                            element === transferSourceBox || element === transferTargetBox);
                    });
                }

                function updateTransferLine() {
                    const visible = transferSourceBox !== null && transferTargetBox !== null;
                    // SVGにはHTML要素のhiddenプロパティがないため属性を操作する。
                    transferLine.toggleAttribute("hidden", !visible);
                    if (!visible) return;
                    [transferSourceBox, transferTargetBox].forEach(function (box, index) {
                        transferLine.setAttribute("x" + (index + 1),
                            scaleX(Number(box.dataset.baseX)));
                        transferLine.setAttribute("y" + (index + 1),
                            scaleY(Number(box.dataset.baseY)) + Number(box.dataset.offsetY || 0));
                    });
                }

                function clearTransfer() {
                    transferSourceBox = null;
                    transferTargetBox = null;
                    updateSelection();
                    updateTransferLine();
                }

                function selectTrain(trainIndex, trainType, kobeTime) {
                    selectedTrainIndex = String(trainIndex);
                    clearTransfer();
                }

                function clearSelectedTrain() {
                    selectedTrainIndex = null;
                    clearTransfer();
                }

                function selectTransfer(targetBox) {
                    const sourceBox = Array.from(svg.querySelectorAll(".diagram-stop-box"))
                        .find(function (box) {
                            return box.dataset.trainIndex === selectedTrainIndex
                                && box.dataset.station === targetBox.dataset.station;
                        });
                    if (!sourceBox) {
                        clearTransfer();
                        return;
                    }
                    transferSourceBox = sourceBox;
                    transferTargetBox = targetBox;
                    updateSelection();
                    updateTransferLine();
                }

                svg.addEventListener("click", function (event) {
                    if (Date.now() < suppressClickUntil) return;
                    const element = event.target.closest("[data-train-index]");
                    if (!element) return;
                    if (element === transferTargetBox) {
                        clearTransfer();
                        return;
                    }
                    if (element.dataset.trainIndex === selectedTrainIndex) {
                        clearSelectedTrain();
                        return;
                    }
                    if (selectedTrainIndex !== null
                        && element.classList.contains("diagram-stop-box")
                        && element.dataset.trainIndex !== selectedTrainIndex) {
                        selectTransfer(element);
                    } else {
                        selectTrain(element.dataset.trainIndex,
                            element.dataset.trainType, element.dataset.kobeTime);
                    }
                });

                const scroller = document.querySelector(".new-diagram-scroll");
                const timeLayer = document.querySelector("#fixed-time-axis g");
                const stationLayer = document.querySelector("#fixed-station-axis g");
                const timeLabels = Array.from(svg.querySelectorAll(".diagram-time-label"));
                const stationLabels = Array.from(svg.querySelectorAll(".diagram-station-name"));
                const timeCopies = timeLabels.map(label => timeLayer.appendChild(label.cloneNode(true)));
                const stationCopies = stationLabels.map(label => stationLayer.appendChild(label.cloneNode(true)));
                function syncAxes() {
                    timeLabels.forEach((label, i) => timeCopies[i].setAttribute("x", label.getAttribute("x")));
                    stationLabels.forEach((label, i) => stationCopies[i].setAttribute("y", label.getAttribute("y")));
                    timeLayer.setAttribute("transform", `translate(${-scroller.scrollLeft} 0)`);
                    stationLayer.setAttribute("transform", `translate(0 ${-scroller.scrollTop})`);
                }
                scroller.addEventListener("scroll", syncAxes, {passive: true});
                updateDiagram();

            }
        );

