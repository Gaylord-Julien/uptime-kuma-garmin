import Toybox.Application;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

// Shows the last stored summary; the background service keeps it fresh.
(:glance)
class KumaGlanceView extends WatchUi.GlanceView {

    function initialize() {
        GlanceView.initialize();
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        var h = dc.getHeight();
        var font = Graphics.FONT_GLANCE;
        var lineH = Graphics.getFontHeight(font);
        var top = (h - 2 * lineH) / 2;

        var summary = Application.Storage.getValue(Kuma.STORAGE_SUMMARY);
        if (!(summary instanceof Dictionary)) {
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            dc.drawText(0, top, font, text(Rez.Strings.AppName), Graphics.TEXT_JUSTIFY_LEFT);
            dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
            dc.drawText(0, top + lineH, font, text(Rez.Strings.NoData), Graphics.TEXT_JUSTIFY_LEFT);
            return;
        }

        var down = summary["d"] as Number;
        var r = lineH / 3;
        var iconX = r;
        var iconY = top + lineH / 2;
        var textX = 2 * r + 8;
        if (down > 0) {
            dc.setColor(Graphics.COLOR_RED, Graphics.COLOR_TRANSPARENT);
            KumaIcons.drawWarning(dc, iconX, iconY, r);
            dc.setColor(Graphics.COLOR_RED, Graphics.COLOR_TRANSPARENT);
            dc.drawText(textX, top, font, Lang.format(text(Rez.Strings.DownCount), [down]), Graphics.TEXT_JUSTIFY_LEFT);
        } else {
            dc.setColor(Graphics.COLOR_GREEN, Graphics.COLOR_TRANSPARENT);
            KumaIcons.drawCheck(dc, iconX, iconY, r);
            dc.setColor(Graphics.COLOR_GREEN, Graphics.COLOR_TRANSPARENT);
            dc.drawText(textX, top, font, text(Rez.Strings.AllUp), Graphics.TEXT_JUSTIFY_LEFT);
        }

        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawText(0, top + lineH, font, Lang.format(text(Rez.Strings.UpdatedAt), [Kuma.formatTime(summary["ts"] as Number)]), Graphics.TEXT_JUSTIFY_LEFT);
    }

    private function text(id as ResourceId) as String {
        return WatchUi.loadResource(id) as String;
    }
}
