"use strict";
const $ = (id) => document.getElementById(id);
// Keep the payload list as JSON for exact HTTP example verification.
// prettier-ignore
const samples = [
  {
    "id": "booking",
    "group": "Visits",
    "title": "Book a technician",
    "hint": "Book the next available slot",
    "subject": "Visit for our cooling problem",
    "body": "Book ticket T001 at the earliest available time."
  },
  {
    "id": "time",
    "group": "Visits",
    "title": "Choose a visit time",
    "hint": "Try a natural date in IST",
    "subject": "Visit on 8 April",
    "body": "Book T001 on 8 april 7:30 PM."
  },
  {
    "id": "unavailableTime",
    "group": "Visits",
    "title": "Unavailable time",
    "hint": "Ask before using another slot",
    "subject": "Visit at 5:30 PM",
    "body": "Book T001 on 8 april 5:30 PM. Check with me before choosing another time."
  },
  {
    "id": "ambiguous",
    "group": "Visits",
    "title": "Unclear equipment",
    "hint": "Ask which unit needs service",
    "subject": "Cooling unit not working",
    "body": "The cooling unit by our loading dock isn't working. Can you send someone?"
  },
  {
    "id": "credit",
    "group": "Credits",
    "title": "Apply a $75 credit",
    "hint": "Credit an eligible invoice",
    "subject": "Service credit",
    "body": "Please apply a $75 service credit to invoice I001 for the delayed response."
  },
  {
    "id": "approval",
    "group": "Credits",
    "title": "Request a $150 credit",
    "hint": "Supervisor approval required",
    "subject": "Service credit",
    "body": "Please credit $150 to I001 for the missed response deadline."
  },
  {
    "id": "hazard",
    "group": "Safety",
    "title": "Smoke from a unit",
    "hint": "Emergency guidance and handoff",
    "subject": "Smoke from the cooling unit",
    "body": "There's smoke coming from the cooling unit at our main loading dock. What should we do?"
  },
  {
    "id": "message",
    "group": "Messages",
    "title": "Write a ticket update",
    "hint": "Write a message to copy",
    "subject": "Service message",
    "body": "Write a message I can send about the current status of T001."
  },
  {
    "id": "namedMessage",
    "group": "Messages",
    "title": "Write to Contact 01",
    "hint": "Use an authorized contact",
    "subject": "Update for our site contact",
    "body": "Write a message I can send to our site contact, named \"Contact 01\", about the current status of T001."
  },
  {
    "id": "bookingMessage",
    "group": "Messages",
    "title": "Book + write an update",
    "hint": "Confirm a visit and prepare text",
    "subject": "Appointment update",
    "body": "Book T001 at the earliest slot and write an appointment update I can send."
  }
];
function node(tag, text, className) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
}
let toastTimer;
function toast(text) {
  $("toast").textContent = text;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").textContent = ""), 2500);
}
// Render a Markdown subset using DOM nodes. Raw HTML stays visible text; links allow HTTP(S) only.
function inline(parent, text) {
  const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\(([^)]+)\))/g;
  let end = 0;
  for (const m of text.matchAll(pattern)) {
    parent.append(document.createTextNode(text.slice(end, m.index)));
    if (m[2]) parent.append(node("strong", m[2]));
    else if (m[3]) parent.append(node("code", m[3]));
    else {
      let url;
      try {
        url = new URL(m[5]);
      } catch {}
      if (url && ["https:", "http:"].includes(url.protocol)) {
        const a = node("a", m[4]);
        a.href = url.href;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        parent.append(a);
      } else parent.append(document.createTextNode(m[0]));
    }
    end = m.index + m[0].length;
  }
  parent.append(document.createTextNode(text.slice(end)));
}
function markdown(text) {
  const container = node("div", undefined, "markdown");
  let list = null,
    quote = null,
    code = null,
    p = null;
  for (const line of text.split("\n")) {
    if (line.startsWith("```")) {
      if (code) {
        code = null;
      } else {
        const pre = node("pre");
        code = node("code", "");
        pre.append(code);
        container.append(pre);
      }
      list = null;
      p = null;
      quote = null;
      continue;
    }
    if (code) {
      code.textContent += line + "\n";
      continue;
    }
    if (!line.trim()) {
      list = null;
      p = null;
      quote = null;
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)/);
    const item = line.match(/^(?:[-*]|\d+\.)\s+(.+)/);
    if (heading) {
      const n = node("h" + Math.min(heading[1].length + 1, 4));
      inline(n, heading[2]);
      container.append(n);
      list = null;
      p = null;
      quote = null;
    } else if (item) {
      const kind = /^\d/.test(line) ? "ol" : "ul";
      if (!list || list.tagName.toLowerCase() !== kind) {
        list = node(kind);
        container.append(list);
      }
      const n = node("li");
      inline(n, item[1]);
      list.append(n);
      p = null;
      quote = null;
    } else if (line.startsWith("> ")) {
      if (!quote) {
        quote = node("blockquote");
        container.append(quote);
      }
      const n = node("p");
      inline(n, line.slice(2));
      quote.append(n);
      p = null;
      list = null;
    } else {
      if (!p) {
        p = node("p");
        container.append(p);
      } else p.append(document.createTextNode(" "));
      inline(p, line);
      list = null;
      quote = null;
    }
  }
  return container;
}
const copyIcon =
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M15 8V4H4v11h4"/></svg>';
function messagePreview(message) {
  const panel = node("section", undefined, "message");
  panel.setAttribute("aria-label", "Copyable message");
  const top = node("div", undefined, "message-top");
  top.append(
    node("span", "Message to copy"),
    node("small", "Not sent or stored"),
  );
  panel.append(top);
  for (const field of ["subject", "body"]) {
    const row = node("div", undefined, "message-row");
    row.append(
      node("span", field === "subject" ? "Subject" : "Message", "row-title"),
      node("p", message[field]),
    );
    const b = node("button", undefined, "copy");
    b.type = "button";
    b.setAttribute("aria-label", `Copy message ${field}`);
    b.title = `Copy ${field}`;
    b.innerHTML = copyIcon; // Constant SVG only; response content never uses innerHTML.
    b.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(message[field]);
        b.textContent = "✓";
        b.setAttribute("aria-label", `${field} copied`);
        toast(`${field === "subject" ? "Subject" : "Message"} copied`);
        setTimeout(() => {
          b.innerHTML = copyIcon;
          b.setAttribute("aria-label", `Copy message ${field}`);
        }, 2000);
      } catch {
        toast(
          "Select the message text to copy. Clipboard access is unavailable.",
        );
      }
    });
    row.append(b);
    panel.append(row);
  }
  return panel;
}

let pending = false;
function empty(title, description) {
  const panel = node("div", undefined, "empty loaded");
  panel.append(
    node("div", "✓", "empty-symbol"),
    node("h3", title),
    node("p", description),
  );
  $("result").replaceChildren(panel);
}
for (const [index, group] of [
  ...new Set(samples.map((s) => s.group)),
].entries()) {
  const options = samples.filter((s) => s.group === group);
  const section = node("details", undefined, "sample-group");
  section.open = index === 0;
  const summary = node("summary");
  summary.append(
    node("span", group),
    node("span", String(options.length), "category-count"),
  );
  section.append(summary);
  section.addEventListener("toggle", () => {
    if (section.open)
      document.querySelectorAll(".sample-group").forEach((other) => {
        if (other !== section) other.open = false;
      });
  });
  const list = node("div", undefined, "sample-options");
  for (const sample of options) {
    const button = node("button", undefined, "sample");
    button.type = "button";
    button.dataset.example = sample.id;
    button.setAttribute("aria-pressed", "false");
    const label = node("span", sample.title);
    label.append(node("small", sample.hint));
    button.append(label, node("span", "Use", "use-label"));
    button.addEventListener("click", () => {
      if (pending) return;
      $("subject").value = sample.subject;
      $("body").value = sample.body;
      document
        .querySelectorAll("[data-example]")
        .forEach((el) =>
          el.setAttribute("aria-pressed", String(el === button)),
        );
      $("selection-note").textContent = "Request loaded.";
      empty("Request loaded", "Select Send request to get a response.");
      if (innerWidth < 761) {
        $("examples").classList.remove("is-open");
        $("browse-examples").setAttribute("aria-expanded", "false");
      }
      $("body").focus({ preventScroll: true });
      if (innerWidth < 761)
        $("compose-panel").scrollIntoView({
          block: "start",
          behavior: "instant",
        });
    });
    list.append(button);
  }
  section.append(list);
  $("sample-list").append(section);
}
$("browse-examples").addEventListener("click", () => {
  const open = $("examples").classList.toggle("is-open");
  $("browse-examples").setAttribute("aria-expanded", String(open));
});
for (const id of ["subject", "body"])
  $(id).addEventListener("input", () => {
    document
      .querySelectorAll("[data-example]")
      .forEach((el) => el.setAttribute("aria-pressed", "false"));
    $("selection-note").textContent = "";
  });
function render(result) {
  const labels = {
    completed: "Completed",
    needs_clarification: "Needs your input",
    escalated: "Human review",
    blocked: "Blocked",
    error: "Unable to complete",
  };
  if (
    !Object.hasOwn(labels, result.status) ||
    typeof result.reply !== "string" ||
    !result.reply.trim() ||
    !Array.isArray(result.evidence) ||
    !result.usage ||
    typeof result.usage !== "object"
  )
    throw new Error("Invalid response");
  const head = node("div", undefined, "outcome-head");
  head.append(
    node(
      "span",
      labels[result.status],
      "badge" +
        (["blocked", "error"].includes(result.status)
          ? " red"
          : result.status === "completed"
            ? ""
            : " amber"),
    ),
  );
  let text = result.reply;
  let message = null;
  // Extract only the action layer's bounded copyable-message envelope. The rest
  // remains the actual reply. Subject/body are removed here to avoid duplication.
  const marker = "Here is a message you can copy and send.";
  const markerIndex = text.indexOf(marker);
  if (
    markerIndex >= 0 &&
    text
      .slice(markerIndex)
      .includes("It has not been sent or saved as a draft.")
  ) {
    const match = text
      .slice(markerIndex)
      .match(/\n\nSubject: ([^\n]+)\n\n([\s\S]+)$/);
    if (match) {
      message = { subject: match[1], body: match[2], recipient: "" };
      text =
        text.slice(0, markerIndex) +
        text.slice(markerIndex, markerIndex + match.index);
    }
  }
  $("result").replaceChildren(head, markdown(text));
  if (message) $("result").append(messagePreview(message));
}
$("composer").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (pending) return;
  const body = $("body").value.trim();
  if (!body) {
    $("body").focus();
    toast("Write a request first.");
    return;
  }
  pending = true;
  const controls = [
    $("run"),
    $("subject"),
    $("body"),
    ...document.querySelectorAll("[data-example]"),
  ];
  controls.forEach((el) => (el.disabled = true));
  $("run").textContent = "Submitting…";
  $("selection-note").textContent = "";
  $("response-panel").setAttribute("aria-busy", "true");
  $("result").replaceChildren(
    node("p", "Checking current records and policy…", "small"),
  );
  try {
    const response = await fetch("/demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ subject: $("subject").value, body }),
    });
    if (!response.ok) throw new Error("Request failed");
    render(await response.json());
  } catch {
    $("result").replaceChildren(
      node("span", "Response unavailable", "badge red"),
      node(
        "p",
        "The response could not be confirmed. Contact operations to reconcile any uncertain action before submitting again.",
        "markdown",
      ),
    );
  } finally {
    pending = false;
    controls.forEach((el) => (el.disabled = false));
    $("run").replaceChildren(
      document.createTextNode("Send request "),
      node("span", "→"),
    );
    $("response-panel").setAttribute("aria-busy", "false");
    if (innerWidth < 761)
      $("response-panel").scrollIntoView({
        block: "start",
        behavior: "instant",
      });
  }
});
