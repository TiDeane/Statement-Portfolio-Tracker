import QtQuick

// Shares a row's width between two cards so that both need about the same height, leaving as little
// empty space inside them as possible. Reads `firstWidth` (0 until worked out). `available` must not
// depend on the cards' own widths, or the two would chase each other.
//
// Each card's height at a given width is estimated from what it holds now: its fixed parts (titles,
// buttons, spacing) plus its wrapping texts and button rows, each needing more lines as it gets
// narrower. The width with the least empty space wins (the shorter card's space below its content),
// with a little weight on the row's height too, so it does not grow much to save a few pixels.
// Worked out again, a moment later, whenever the cards' contents or the row's width change.
Item {
    id: balancer
    property Item first
    property Item second
    property real available: 0  // the row's width, without the gap between the cards
    property real minimum: 280
    property real firstWidth: 0

    visible: false
    property int tries: 0
    function refresh() { tries = 0; later.restart() }
    onAvailableChanged: refresh()
    Connections {
        target: balancer.first
        function onImplicitHeightChanged() { balancer.refresh() }
    }
    Connections {
        target: balancer.second
        function onImplicitHeightChanged() { balancer.refresh() }
    }
    Timer {  // a moment later: once the cards have been laid out at their new size
        id: later
        interval: 30
        onTriggered: balancer.balance()
    }

    // What in `item` gets taller when it gets narrower: wrapping texts and rows of buttons that wrap.
    function wrapping(item, found) {
        for (var i = 0; i < item.children.length; i++) {
            var child = item.children[i]
            if (!child.visible)
                continue
            if (child.flow !== undefined && child.spacing !== undefined) {  // a Flow
                found.push({ item: child, flow: true })
            } else if (child.lineCount !== undefined && child.wrapMode !== undefined
                       && child.wrapMode !== Text.NoWrap && child.text !== "") {
                found.push({ item: child, flow: false })
            } else {
                wrapping(child, found)
            }
        }
        return found
    }

    TextMetrics { id: metrics }

    // How many lines `text` takes at `width`: each of its paragraphs measured on its own.
    function linesOfText(text, width) {
        var room = Math.max(1, width - text.leftPadding - text.rightPadding)
        var paragraphs = String(text.text).split("\n"), lines = 0
        metrics.font = text.font
        for (var i = 0; i < paragraphs.length; i++) {
            metrics.text = paragraphs[i]
            var natural = metrics.advanceWidth * 1.06  // a little more: lines break between words
            lines += Math.max(1, Math.ceil(natural / room))
        }
        return lines
    }

    function heightOfFlow(flow, width) {
        var rows = 1, used = 0, rowHeight = 0
        for (var i = 0; i < flow.children.length; i++) {
            var child = flow.children[i]
            if (!child.visible || child.width <= 0)
                continue
            rowHeight = Math.max(rowHeight, child.height)
            if (used > 0 && used + flow.spacing + child.width > width) {
                rows += 1
                used = child.width
            } else {
                used += (used > 0 ? flow.spacing : 0) + child.width
            }
        }
        return rows * rowHeight + (rows - 1) * flow.spacing
    }

    // A card's height at `width`, from how it is laid out now.
    function estimate(card) {
        var parts = wrapping(card, [])
        var fixed = card.implicitHeight
        for (var i = 0; i < parts.length; i++)
            fixed -= parts[i].item.height
        return function (width) {
            var height = fixed
            for (var i = 0; i < parts.length; i++) {
                var part = parts[i].item
                var partWidth = part.width + (width - card.width)  // what is beside it keeps its width
                if (parts[i].flow) {
                    height += heightOfFlow(part, partWidth)
                } else {
                    var line = part.lineCount > 0 ? part.contentHeight / part.lineCount : part.font.pixelSize * 1.4
                    var padding = part.height - part.lineCount * line
                    height += padding + linesOfText(part, partWidth) * line
                }
            }
            return height
        }
    }

    function balance() {
        if (!first || !second || first.width <= 0 || second.width <= 0 || available < 2 * minimum)
            return
        var firstHeight = estimate(first), secondHeight = estimate(second)
        var settled = Math.abs(firstHeight(first.width) - first.implicitHeight) <= 2
            && Math.abs(secondHeight(second.width) - second.implicitHeight) <= 2
        if (!settled && tries < 10) {  // still being laid out: measured again shortly
            tries += 1
            later.restart()
            return
        }
        var widths = [], heights = [], lowest = Infinity
        for (var width = minimum; width <= available - minimum; width += 4) {
            var a = firstHeight(width), b = secondHeight(available - width)
            widths.push(width)
            heights.push([a, b])
            lowest = Math.min(lowest, Math.max(a, b))
        }
        var best = first.width, bestCost = Infinity
        for (var i = 0; i < widths.length; i++) {
            var empty = Math.abs(heights[i][0] - heights[i][1])
            var cost = empty + 0.3 * (Math.max(heights[i][0], heights[i][1]) - lowest)
            var better = cost < bestCost - 0.5
                || (Math.abs(cost - bestCost) <= 0.5 && Math.abs(widths[i] - first.width) < Math.abs(best - first.width))
            if (better) {
                best = widths[i]
                bestCost = cost
            }
        }
        if (Math.abs(best - firstWidth) >= 1)
            firstWidth = best
    }
}
