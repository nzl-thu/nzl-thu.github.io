---
layout: page
permalink: /honors/
title: honors
description: Awards, scholarships, research grants, and talent programs.
nav: true
nav_order: 4
---

{% assign section_titles = 'Honors and Awards|Research Grants and Programs' | split: '|' %}

<div class="cv">
  {% for section_title in section_titles %}
    {% assign entry = site.data.cv | where: 'title', section_title | first %}
    <section class="card mt-3 p-3">
      <h2 class="card-title font-weight-medium">{{ entry.title }}</h2>
      {% include cv/time_table.liquid %}
    </section>
  {% endfor %}
</div>
