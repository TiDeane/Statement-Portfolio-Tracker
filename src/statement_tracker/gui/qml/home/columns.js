.pragma library

// How wide each column of the investments list is, by its key (settings.TABLE_COLUMNS, and "name").
// The heading row and every row lay their cells out with these, so the columns line up.

var margin = 20
var spacing = 16

// The part of the spare width each column takes.
var stretch = {
    name: 22, shares: 9, average_cost: 11, price: 10, invested: 11, worth: 12,
    share: 13, invested_share: 10, gain: 15, realized: 12, dividends: 11
}

// Below this a column does not shrink: the list scrolls sideways instead.
var minimum = {
    name: 140, shares: 95, average_cost: 90, price: 80, invested: 80, worth: 90,
    share: 100, invested_share: 80, gain: 175, realized: 100, dividends: 90
}

// The least width of a column, given the columns shown: Worth now makes room for "Enter its value…"
// when Gain or loss, where that button usually is, is hidden.
function minimumFor(key, columns) {
    if (key === "worth" && columns.indexOf("gain") < 0)
        return 150
    return minimum[key]
}

// Texts and bars start on the left; amounts end on the right.
function leftAligned(key) {
    return key === "name" || key === "share"
}

// Each column's least width (key -> pixels) given the columns shown and the longest text of each,
// `widest` (key -> text), measured with `metrics` (a FontMetrics in the table's font): never narrower
// than its text, so no amount spills into the next column, whatever the font. A share's bar adds 66.
function minimums(columns, widest, metrics) {
    var result = { name: minimum.name }
    for (var i = 0; i < columns.length; i++) {
        var key = columns[i]
        var text = Math.ceil(metrics.advanceWidth(widest[key] || "")) + 6 + (key === "share" ? 66 : 0)
        result[key] = Math.max(minimumFor(key, columns), text)
    }
    return result
}

// The width the name and `columns` need at the least, with their `widths` from minimums().
function needed(columns, widths) {
    var width = 2 * margin + widths.name
    for (var i = 0; i < columns.length; i++)
        width += spacing + widths[columns[i]]
    return width
}

// A column's least width from minimums(), or its usual one before those are known.
function widthOf(key, columns, widths) {
    return widths && widths[key] !== undefined ? widths[key] : minimumFor(key, columns)
}
