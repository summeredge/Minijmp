(function () {
  "use strict";
  const topics = window.MINIJMP_HELP_INDEX || [];
  const byId = new Map(topics.map(topic => [topic.id, topic]));
  const directory = document.getElementById("directory");
  const chapter = document.getElementById("chapter");
  const locationLabel = document.getElementById("location");
  const search = document.getElementById("search");
  const results = document.getElementById("search-results");
  const groups = new Map();
  const directoryLinks = new Map();

  topics.forEach(topic => {
    if (!groups.has(topic.category)) groups.set(topic.category, []);
    groups.get(topic.category).push(topic);
  });
  groups.forEach((items, category) => {
    const details = document.createElement("details");
    details.className = "directory-group";
    details.open = true;
    const summary = document.createElement("summary");
    summary.textContent = category;
    const list = document.createElement("ul");
    items.forEach(topic => {
      const row = document.createElement("li");
      const link = document.createElement("a");
      link.href = "#" + encodeURIComponent(topic.id);
      link.dataset.topic = topic.id;
      link.textContent = topic.title;
      directoryLinks.set(topic.id, link);
      row.appendChild(link);
      list.appendChild(row);
    });
    details.append(summary, list);
    directory.appendChild(details);
  });

  function navigate(id, updateHash) {
    const topic = byId.get(id);
    if (!topic) {
      if (id) {
        locationLabel.textContent = "未找到该帮助章节";
      } else {
        chapter.src = "pages/home.html";
        locationLabel.textContent = "帮助首页";
      }
      directory.querySelectorAll("a[aria-current]").forEach(link => link.removeAttribute("aria-current"));
      return;
    }
    chapter.src = topic.page;
    locationLabel.textContent = topic.title;
    directory.querySelectorAll("a[aria-current]").forEach(link => link.removeAttribute("aria-current"));
    const active = directoryLinks.get(topic.id);
    if (active) {
      active.setAttribute("aria-current", "page");
      active.closest("details").open = true;
    }
    if (updateHash && location.hash !== "#" + encodeURIComponent(topic.id)) location.hash = topic.id;
  }

  function hashTopic() {
    try { return decodeURIComponent(location.hash.slice(1)); }
    catch (_) { return ""; }
  }

  function showResults(query) {
    results.replaceChildren();
    if (!query) {
      results.hidden = true;
      return;
    }
    const needle = query.toLocaleLowerCase();
    const matches = topics.filter(topic => (topic.title + " " + topic.text).toLocaleLowerCase().includes(needle));
    const count = document.createElement("p");
    count.textContent = matches.length ? `找到 ${matches.length} 个帮助章节` : "没有匹配的内容";
    results.appendChild(count);
    matches.forEach(topic => {
      const button = document.createElement("button");
      button.type = "button";
      const title = document.createElement("strong");
      title.textContent = topic.title;
      const excerpt = document.createElement("small");
      excerpt.textContent = topic.text.slice(0, 180);
      button.append(title, excerpt);
      button.addEventListener("click", () => {
        results.hidden = true;
        search.value = "";
        navigate(topic.id, true);
      });
      results.appendChild(button);
    });
    results.hidden = false;
  }

  search.addEventListener("input", () => showResults(search.value.trim()));
  search.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      search.value = "";
      showResults("");
      search.blur();
    }
  });
  document.getElementById("home-link").addEventListener("click", event => {
    event.preventDefault();
    if (location.hash) location.hash = "";
    navigate(null, false);
  });
  window.addEventListener("hashchange", () => navigate(hashTopic(), false));
  navigate(hashTopic(), false);
}());
