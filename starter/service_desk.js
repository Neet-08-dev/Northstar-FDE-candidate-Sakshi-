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
    "id": "intake",
    "onlyFor": "C001",
    "group": "Tickets",
    "title": "Record an interruption",
    "hint": "Create a ticket without a visit",
    "subject": "Cooling problem at the annex",
    "body": "The annex cooling unit at Aster Foods Annex Loading Dock has stopped cooling. Please log the problem. We'll arrange a visit later."
  },
  {
    "id": "intakeBooking",
    "onlyFor": "C001",
    "group": "Tickets",
    "title": "Maintenance and visit",
    "hint": "Record the issue and book service",
    "subject": "Maintenance for the annex cooling unit",
    "body": "We'd like routine maintenance for the cooling unit at our Aster Foods annex. Please send someone at the next available time."
  },
  {
    "id": "reuseTicket",
    "group": "Tickets",
    "title": "Use an open ticket",
    "hint": "Avoid a duplicate ticket",
    "subject": "Cooling problem at our main loading dock",
    "body": "HVAC unit 01 at Aster Foods Loading Dock has stopped cooling. Please log the problem against any open ticket for that unit. We will arrange a visit later."
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
    "id": "missingAmount",
    "group": "Credits",
    "title": "Credit without an amount",
    "hint": "Ask for an exact credit amount",
    "subject": "Credit for our delayed service",
    "body": "Please apply a service credit to invoice I001 for the delayed response."
  },
  {
    "id": "ineligibleCredit",
    "group": "Credits",
    "title": "Credit over invoice total",
    "hint": "Ask before reducing the amount",
    "subject": "Request for a $600 service credit",
    "body": "Please apply a $600 service credit to invoice I001 for the delayed response."
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
  },
  {
    "id": "unauthorizedMessage",
    "onlyFor": "C001",
    "group": "Messages",
    "title": "Update for a contractor",
    "hint": "Check recipient authorization",
    "subject": "Ticket update for our contractor",
    "body": "Write a message I can send to the contact listed as Unapproved contractor about the current status of T001."
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

// Demo customers. The presenter chooses whose session the request runs in; the
// server turns that choice into the session actor. Examples are written for the
// default customer. For another customer, references to the default customer's
// primary records become that customer's own. Examples that need records only
// the default customer has keep their text and show access scoping instead.
const customerKey = "northstar.demoCustomer";
let catalog = null;
let customer = null;
let loadedSample = samples.find((s) => s.id === "booking");
const sampleTags = new Map();
function primaryRecords(c) {
  return [
    c.sites[0]?.name,
    c.assets[0]?.label,
    c.contacts.find((contact) => contact.authorized)?.name,
    c.tickets[0]?.id,
    c.invoices[0]?.id,
  ];
}
function forCustomer(sample) {
  const text = { subject: sample.subject, body: sample.body };
  if (!catalog || !customer || customer.id === catalog.default || sample.onlyFor)
    return text;
  const base = catalog.customers.find((c) => c.id === catalog.default);
  const target = primaryRecords(customer);
  const swaps = new Map();
  primaryRecords(base).forEach((from, i) => {
    if (from && target[i]) swaps.set(from, target[i]);
  });
  if (!swaps.size) return text;
  const pattern = new RegExp(
    `\\b(${[...swaps.keys()]
      .sort((a, b) => b.length - a.length)
      .map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
      .join("|")})\\b`,
    "g",
  );
  for (const field of ["subject", "body"])
    text[field] = text[field].replace(pattern, (m) => swaps.get(m));
  return text;
}
function money(cents, currency) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
  }).format(cents / 100);
}
function renderAccount() {
  $("account-name").textContent = customer.name;
  $("account-meta").textContent = [
    customer.id,
    customer.tier,
    customer.account_status,
  ].join(" · ");
  const records = $("account-records");
  records.replaceChildren();
  const section = (title, rows) => {
    if (!rows.length) return;
    records.append(node("dt", title));
    for (const [id, label, meta] of rows) {
      const row = node("dd");
      row.append(node("code", id), document.createTextNode(label));
      if (meta) row.append(node("span", meta));
      records.append(row);
    }
  };
  section(
    "Tickets",
    customer.tickets.map((t) => [t.id, t.summary, `${t.status} · ${t.severity}`]),
  );
  section(
    "Invoices",
    customer.invoices.map((i) => [i.id, money(i.total_cents, i.currency), i.status]),
  );
  section(
    "Sites",
    customer.sites.map((s) => [s.id, s.name, s.access_window]),
  );
  section(
    "Equipment",
    customer.assets.map((a) => [a.id, a.label, a.required_skill]),
  );
  section(
    "Contacts",
    customer.contacts.map((c) => [
      c.id,
      c.name,
      c.authorized ? "authorized" : "not authorized",
    ]),
  );
  $("account").hidden = false;
}
function refreshSamples() {
  const base = catalog?.customers.find((c) => c.id === catalog.default);
  for (const [sample, tag] of sampleTags) {
    tag.hidden = !customer || !sample.onlyFor || sample.onlyFor === customer.id;
    tag.textContent = `Uses ${base?.name ?? "default"} records`;
  }
  if (loadedSample) {
    const text = forCustomer(loadedSample);
    $("subject").value = text.subject;
    $("body").value = text.body;
  }
}
function setCustomer(id, announce) {
  customer = catalog.customers.find((c) => c.id === id);
  try {
    localStorage.setItem(customerKey, id);
  } catch {}
  renderAccount();
  refreshSamples();
  if (announce)
    empty(
      `Requesting as ${customer.name}`,
      "Requests now run in this customer's session.",
    );
}
async function loadCustomers() {
  const select = $("customer");
  try {
    const response = await fetch("/demo/customers");
    if (!response.ok) throw new Error("Customers unavailable");
    catalog = await response.json();
    const groups = new Map();
    for (const c of catalog.customers) {
      const tier = c.tier.charAt(0).toUpperCase() + c.tier.slice(1);
      if (!groups.has(tier)) {
        const group = node("optgroup");
        group.label = tier;
        groups.set(tier, group);
      }
      const option = node("option", `${c.name} · ${c.id}`);
      option.value = c.id;
      groups.get(tier).append(option);
    }
    select.replaceChildren(...groups.values());
    let saved = null;
    try {
      saved = localStorage.getItem(customerKey);
    } catch {}
    const initial =
      catalog.customers.find((c) => c.id === saved) ??
      catalog.customers.find((c) => c.id === catalog.default);
    select.value = initial.id;
    select.disabled = false;
    setCustomer(initial.id, false);
  } catch {
    catalog = null;
    customer = null;
    select.replaceChildren(node("option", "Default demo customer"));
    select.disabled = true;
    select.title = "Customer list unavailable";
  }
}
$("customer").addEventListener("change", (event) => {
  if (pending) return;
  endConversation();
  setCustomer(event.target.value, true);
});

// Follow-ups: one conversation keeps one synthetic session on the server, and the
// last few turns are sent back as untrusted context for the model.
let conversation = null;
function conversationId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return Array.from({ length: 4 }, () =>
    Math.random().toString(36).slice(2, 10).padEnd(8, "0"),
  ).join("-");
}
function endConversation() {
  if (conversation)
    fetch("/demo/end", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversation.id }),
    }).catch(() => {});
  conversation = null;
  $("new-conversation").hidden = true;
  $("body").placeholder = "";
}
function thread(turns) {
  const box = node("details", undefined, "thread");
  box.append(
    node(
      "summary",
      `Earlier in this conversation (${turns.length} ${turns.length === 1 ? "turn" : "turns"})`,
    ),
  );
  for (const turn of turns) {
    const item = node("div", undefined, "thread-turn");
    item.append(
      node("p", `You: ${turn.body}`, "thread-you"),
      node(
        "p",
        `Assistant: ${turn.reply.length > 280 ? turn.reply.slice(0, 280) + "…" : turn.reply}`,
        "thread-assistant",
      ),
    );
    box.append(item);
  }
  return box;
}
$("new-conversation").addEventListener("click", () => {
  if (pending) return;
  endConversation();
  $("body").value = "";
  $("selection-note").textContent = "New conversation started.";
  empty("New conversation", "Write a request or choose an example.");
  $("body").focus();
});

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
    if (sample.onlyFor) {
      const tag = node("span", undefined, "tag warn");
      tag.hidden = true;
      sampleTags.set(sample, tag);
      label.append(tag);
    }
    button.append(label, node("span", "Use", "use-label"));
    button.addEventListener("click", () => {
      if (pending) return;
      endConversation();
      loadedSample = sample;
      const text = forCustomer(sample);
      $("subject").value = text.subject;
      $("body").value = text.body;
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
    loadedSample = null;
    document
      .querySelectorAll("[data-example]")
      .forEach((el) => el.setAttribute("aria-pressed", "false"));
    $("selection-note").textContent = "";
  });
function render(result, asCustomer, earlier = []) {
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
  if (asCustomer)
    head.append(
      node("span", `As ${asCustomer.name} · ${asCustomer.id}`, "as-customer"),
    );
  // The server returns any prepared message as structured fields, with the
  // reply text that precedes it, so the reply prose is never parsed here.
  const message =
    result.message &&
    typeof result.message === "object" &&
    ["subject", "body", "preface"].every(
      (key) => typeof result.message[key] === "string",
    )
      ? result.message
      : null;
  const text = message ? message.preface : result.reply;
  $("result").replaceChildren(head, markdown(text));
  if (message) $("result").append(messagePreview(message));
  if (earlier.length) $("result").prepend(thread(earlier));
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
  if (catalog) controls.push($("customer"));
  controls.push($("new-conversation"));
  controls.forEach((el) => (el.disabled = true));
  $("run").textContent = "Submitting…";
  $("selection-note").textContent = "";
  $("response-panel").setAttribute("aria-busy", "true");
  $("result").replaceChildren(
    node("p", "Checking current records and policy…", "pending"),
  );
  const asCustomer = customer;
  conversation ??= { id: conversationId(), turns: [] };
  const current = conversation;
  const subject = $("subject").value;
  const payload = {
    subject,
    body,
    conversation_id: current.id,
    history: current.turns.slice(-4),
  };
  if (asCustomer) payload.customer_id = asCustomer.id;
  try {
    const response = await fetch("/demo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("Request failed");
    const result = await response.json();
    render(result, asCustomer, current.turns.slice(-4));
    if (conversation === current) {
      current.turns.push({ subject, body, reply: result.reply });
      $("new-conversation").hidden = false;
      $("body").value = "";
      $("body").placeholder = "Reply here to continue this conversation…";
      loadedSample = null;
      document
        .querySelectorAll("[data-example]")
        .forEach((el) => el.setAttribute("aria-pressed", "false"));
    }
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
loadCustomers();
