---
layout: page
permalink: /publications/
title: publications
description: 21 research works, including 11 first/co-first-author works. An asterisk (*) denotes equal contribution.
nav: true
nav_order: 2
---

<!-- _pages/publications.md -->

<!-- Bibsearch Feature -->

{% include bib_search.liquid %}

<div class="publications">

<h2>First / co-first author</h2>

{% bibliography -q @*[first_author=true] %}

<h2>Collaborative works</h2>

{% bibliography -q @*[first_author=false] %}

</div>
