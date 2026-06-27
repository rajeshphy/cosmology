---
layout: default
title: Cosmology Brief
---

<h1>Cosmology Brief</h1>

<div class="post-list">
{% for post in site.posts %}
  <a class="post-row" href="{{ post.url | relative_url }}">
    <time datetime="{{ post.date | date_to_xmlschema }}">{{ post.date | date: "%Y-%m-%d" }}</time>
    <span>{{ post.summary | default: post.title }}</span>
  </a>
{% else %}
  <p class="empty-list">No briefs yet.</p>
{% endfor %}
</div>
