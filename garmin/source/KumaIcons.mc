import Toybox.Graphics;
import Toybox.Lang;

// ✓ and ⚠ drawn with primitives: system fonts don't reliably carry those glyphs.
// Both use the current foreground colour.
(:glance)
module KumaIcons {

    function drawCheck(dc as Graphics.Dc, x as Number, y as Number, r as Number) as Void {
        dc.fillCircle(x, y, r);
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(r / 4 + 1);
        dc.drawLine(x - r / 2, y, x - r / 8, y + r * 3 / 8);
        dc.drawLine(x - r / 8, y + r * 3 / 8, x + r / 2, y - r * 3 / 8);
        dc.setPenWidth(1);
    }

    function drawWarning(dc as Graphics.Dc, x as Number, y as Number, r as Number) as Void {
        dc.fillPolygon([[x, y - r], [x + r, y + r * 4 / 5], [x - r, y + r * 4 / 5]]);
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_TRANSPARENT);
        var w = r / 4 + 1;
        dc.fillRectangle(x - w / 2, y - r / 3, w, r * 2 / 3);
        dc.fillRectangle(x - w / 2, y + r * 2 / 5, w, w);
    }
}
