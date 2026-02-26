function lockScroll() {

    const body = document.body;

    // evita doppia applicazione
    if (body.classList.contains("scroll-locked")) return;

    const scrollBarWidth = window.innerWidth - document.documentElement.clientWidth;

    if (scrollBarWidth > 0) {
        body.style.paddingRight = scrollBarWidth + "px";
    }

    body.classList.add("overflow-hidden");
    body.classList.add("scroll-locked");
}

function unlockScroll() {

    const body = document.body;

    body.style.paddingRight = "";
    body.classList.remove("overflow-hidden");
    body.classList.remove("scroll-locked");
}

function addCategory(name) {

    const container = document.getElementById("selected-categories");
    const hidden = document.getElementById("categories-hidden");

    const currentCategories = hidden.value ? hidden.value.split(",") : [];

    if (currentCategories.includes(name)) return;

    // Crea tag
    const tag = document.createElement("div");
    tag.className = "bg-blue-100 px-2 py-1 rounded flex items-center gap-2";

    const text = document.createElement("span");
    text.innerText = name;

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.innerHTML = "✕";
    removeBtn.className = "text-blue-700 hover:text-red-600 font-bold";
    removeBtn.style.cursor = "pointer";

    removeBtn.onclick = function () {
        removeCategory(name, tag);
    };

    tag.appendChild(text);
    tag.appendChild(removeBtn);
    container.appendChild(tag);

    currentCategories.push(name);
    hidden.value = currentCategories.join(",");
}

function removeCategory(name, tagElement) {

    const hidden = document.getElementById("categories-hidden");

    let categories = hidden.value ? hidden.value.split(",") : [];

    categories = categories.filter(c => c !== name);

    hidden.value = categories.join(",");

    tagElement.remove();
}


function selectCategory(name) {
    addCategory(name);
    document.getElementById("category-results").innerHTML = "";
}

function initSelectedCategories() {

    const hidden = document.getElementById("categories-hidden");
    const container = document.getElementById("selected-categories");

    if (!hidden || !container) return;

    container.innerHTML = "";

    if (!hidden.value) return;

    hidden.value.split(",").forEach(cat => {

        const clean = cat.trim();
        if (!clean) return;

        const tag = document.createElement("div");
        tag.className = "bg-blue-100 px-2 py-1 rounded flex items-center gap-2";

        const text = document.createElement("span");
        text.innerText = clean;

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.innerHTML = "✕";
        removeBtn.className = "text-blue-700 hover:text-red-600 font-bold";
        removeBtn.style.cursor = "pointer";

        removeBtn.onclick = function () {
            removeCategory(clean, tag);
        };

        tag.appendChild(text);
        tag.appendChild(removeBtn);
        container.appendChild(tag);
    });
}

function closeModal() {
    const container = document.getElementById('modal-container');
    if (container) container.innerHTML = '';
    unlockScroll();
}

document.body.addEventListener("htmx:afterSwap", function () {
    initSelectedCategories();
});

document.addEventListener("DOMContentLoaded", function () {
    initSelectedCategories();
});

document.body.addEventListener('htmx:afterSwap', function (e) {
    if (e.target.id === 'modal-container') {

        const hasModal = e.target.querySelector('.fixed');

        if (hasModal) {
            lockScroll();
        } else {
            unlockScroll();
        }
    }
});

/* DROPDOWN MANAGER */
document.addEventListener("click", function (e) {

    document.querySelectorAll("[data-dropdown]").forEach(drop => {

        const triggerId = drop.dataset.trigger;
        const trigger = document.getElementById(triggerId);

        if (!trigger) return;

        const clickInsideDropdown = drop.contains(e.target);
        const clickOnTrigger = trigger.contains(e.target);

        if (!clickInsideDropdown && !clickOnTrigger) {
            drop.innerHTML = "";
        }

    });

});

function closeCategoryDropdown() {
    setTimeout(() => {
        document.getElementById("category-results").innerHTML = "";
    }, 150);
}