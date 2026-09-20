document.querySelectorAll(".password-toggle").forEach(function (button) {
    button.addEventListener("click", function () {
        var input = document.getElementById(button.dataset.target);
        if (!input) return;

        var showing = input.type === "text";
        input.type = showing ? "password" : "text";
        button.textContent = showing ? "Show" : "Hide";
        button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
});