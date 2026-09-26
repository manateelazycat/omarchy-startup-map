function words(value) {
  return String(value || "").toLowerCase().replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[._:/\\-]+/g, " ").split(/[^a-z0-9\u0080-\uffff]+/).filter(Boolean)
}

function score(entry, query) {
  var name = String(entry.name || "").toLowerCase()
  var id = String(entry.id || "").toLowerCase()
  var generic = String(entry.genericName || "").toLowerCase()
  var comment = String(entry.comment || "").toLowerCase()
  var keywords = entry.keywords && typeof entry.keywords.join === "function"
    ? entry.keywords.join(" ").toLowerCase() : ""
  var q = String(query || "").trim().toLowerCase()
  if (!q) return 0
  var terms = q.split(/\s+/)
  var haystack = [name, id, generic, comment, keywords].join(" ")
  var acronym = words([name, id, generic, keywords].join(" ")).map(function(word) {
    return word.charAt(0)
  }).join("")
  for (var i = 0; i < terms.length; i++) {
    if (haystack.indexOf(terms[i]) < 0 && acronym.indexOf(terms[i]) < 0) return -1
  }
  if (name.indexOf(q) === 0) return 10000 - name.length
  if (id.indexOf(q) === 0) return 9500 - id.length
  if (name.indexOf(q) >= 0) return 8000 - name.indexOf(q) * 10
  if (id.indexOf(q) >= 0) return 7500 - id.indexOf(q) * 10
  if (acronym.indexOf(q) === 0) return 5000
  return 3000
}

function filtered(entries, query) {
  var rows = []
  for (var i = 0; i < entries.length; i++) {
    var entry = entries[i]
    if (!entry || entry.noDisplay || !entry.name || !entry.execString) continue
    var rank = score(entry, query)
    if (rank < 0) continue
    rows.push({ entry: entry, rank: rank, name: String(entry.name).toLowerCase() })
  }
  rows.sort(function(a, b) { return b.rank - a.rank || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0) })
  return rows.slice(0, 40)
}

if (typeof module !== "undefined") module.exports = { words, score, filtered }
