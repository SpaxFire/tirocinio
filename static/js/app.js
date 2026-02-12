document.body.addEventListener("htmx:afterOnLoad", function (evt) {

    const url = window.location.pathname;

    document.querySelectorAll(".nav-link").forEach(link => {
        link.classList.remove("bg-gray-200");
        if (link.getAttribute("hx-get") === url) {
            link.classList.add("bg-gray-200");
        }
    });

});

function setActiveMenu() {
    const url = window.location.pathname;

    document.querySelectorAll(".nav-link").forEach(link => {
        link.classList.remove("bg-gray-200");
        if (link.getAttribute("hx-get") === url) {
            link.classList.add("bg-gray-200");
        }
    });
}

document.addEventListener("DOMContentLoaded", setActiveMenu);
document.body.addEventListener("htmx:afterOnLoad", setActiveMenu);

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
