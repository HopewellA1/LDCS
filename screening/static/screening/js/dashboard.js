/* =========================================================================
   Disability Unit dashboard charts. Reads the data Django embedded as JSON
   in <script id="charts-data"> and draws each chart with Chart.js.
   Plain, commented, one function per chart.
   ========================================================================= */

(function () {
    "use strict";

    // Read the data the server put on the page.
    var el = document.getElementById("charts-data");
    if (!el || typeof Chart === "undefined") {
        return; // nothing to draw, or Chart.js failed to load
    }
    var data = JSON.parse(el.textContent);

    // House palette (kept in step with the site's navy + status colours).
    var NAVY = "#1f4f8f";
    var AMBER = "#f59e0b";   // flagged
    var GREEN = "#12b76a";   // clear
    var GREY = "#cbd5e1";    // "not" / empty
    var INK = "#344054";

    Chart.defaults.font.family = "Arial, Helvetica, sans-serif";
    Chart.defaults.color = INK;

    function byId(id) {
        return document.getElementById(id);
    }

    // --- A horizontal single-hue bar (magnitude by category) ---
    function horizontalBar(canvasId, labels, values) {
        var c = byId(canvasId);
        if (!c) return;
        new Chart(c, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: NAVY,
                    borderRadius: 4,
                    borderSkipped: false,
                }],
            },
            options: {
                indexAxis: "y",
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef1f5" } },
                    y: { grid: { display: false } },
                },
            },
        });
    }

    // --- A vertical single-hue bar (distribution) ---
    function verticalBar(canvasId, labels, values) {
        var c = byId(canvasId);
        if (!c) return;
        new Chart(c, {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: NAVY,
                    borderRadius: 4,
                    borderSkipped: false,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, title: { display: true, text: "Number of flags" } },
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#eef1f5" } },
                },
            },
        });
    }

    // --- A two-slice donut (a single proportion) ---
    function donut(canvasId, labels, values, colours) {
        var c = byId(canvasId);
        if (!c) return;
        new Chart(c, {
            type: "doughnut",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colours,
                    borderColor: "#ffffff",
                    borderWidth: 2,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "62%",
                plugins: {
                    legend: { position: "bottom" },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                var total = ctx.dataset.data.reduce(function (a, b) { return a + b; }, 0);
                                var pct = total ? Math.round(ctx.parsed / total * 100) : 0;
                                return ctx.label + ": " + ctx.parsed + " (" + pct + "%)";
                            },
                        },
                    },
                },
            },
        });
    }

    // --- A tiny sparkline (monthly trend), no axes or legend ---
    function sparkline(canvasId, values) {
        var c = byId(canvasId);
        if (!c) return;
        new Chart(c, {
            type: "line",
            data: {
                labels: values.map(function (_, i) { return i; }),
                datasets: [{
                    data: values,
                    borderColor: NAVY,
                    backgroundColor: "rgba(31, 79, 143, 0.12)",
                    borderWidth: 2,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 0,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { enabled: false } },
                scales: { x: { display: false }, y: { display: false } },
                elements: { line: { borderJoinStyle: "round" } },
            },
        });
    }

    // --- Draw everything ---
    horizontalBar("chart-domain", data.domain.labels, data.domain.data);
    verticalBar("chart-distribution", data.distribution.labels, data.distribution.data);
    horizontalBar("chart-faculty", data.faculty.labels, data.faculty.data);
    donut("chart-flagged", data.flagged.labels, data.flagged.data, [AMBER, GREEN]);
    donut("chart-referred", data.referred.labels, data.referred.data, [NAVY, GREY]);
    sparkline("spark-screened", data.trend.screened);
    sparkline("spark-flagged", data.trend.flagged);
})();
