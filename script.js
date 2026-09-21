document.addEventListener("DOMContentLoaded", () => {
    const sucCode = document.getElementById("sucCode");
    const sucHint = document.getElementById("sucHint");

    if (sucCode) {
        sucCode.addEventListener("input", () => {
            sucCode.value = sucCode.value.replace(/\D/g, "").slice(0, 10);
            sucHint.textContent = sucCode.value.length === 10
                ? "✓ 10-digit SUC Code"
                : `${sucCode.value.length}/10 digits`;
        });
    }

    const form = document.getElementById("registrationForm");
    const submitButton = document.getElementById("submitButton");

    if (form && submitButton) {
        form.addEventListener("submit", (event) => {
            const requiredFields = form.querySelectorAll("[required]");
            let valid = true;

            requiredFields.forEach((field) => {
                if (!field.value.trim()) valid = false;
            });

            if (sucCode && !/^\d{10}$/.test(sucCode.value)) {
                valid = false;
                sucHint.textContent = "Please enter exactly 10 digits.";
            }

            if (!valid) {
                event.preventDefault();
                return;
            }

            submitButton.disabled = true;
            submitButton.textContent = "SUBMITTING...";
        });
    }

    const search = document.getElementById("adminSearch");
    const table = document.getElementById("registrationTable");

    if (search && table) {
        search.addEventListener("input", () => {
            const query = search.value.toLowerCase().trim();
            table.querySelectorAll("tbody tr").forEach((row) => {
                row.style.display = row.innerText.toLowerCase().includes(query) ? "" : "none";
            });
        });
    }
});
