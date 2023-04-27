﻿document.getElementById("step1-link").addEventListener("click", function () {
    showContent("step1");
});

document.getElementById("step2-link").addEventListener("click", function () {
    showContent("step2");
});

document.getElementById("step3-link").addEventListener("click", function () {
    showContent("step3");
});

document.getElementById("step4-link").addEventListener("click", function () {
    showContent("step4");
});


function showContent(id) {
    var sections = document.getElementsByClassName("content-section");

    for (var i = 0; i < sections.length; i++) {
        sections[i].style.display = "none";
    }

    document.getElementById(id).style.display = "block";
}

