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

// Texts and bars start on the left; amounts end on the right.
function leftAligned(key) {
    return key === "name" || key === "share"
}

// The width the name and `columns` need at the least.
function needed(columns) {
    var width = 2 * margin + minimum.name
    for (var i = 0; i < columns.length; i++)
        width += spacing + minimum[columns[i]]
    return width
}
