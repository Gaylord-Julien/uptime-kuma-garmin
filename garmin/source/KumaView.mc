import Toybox.Application;
import Toybox.Communications;
import Toybox.Graphics;
import Toybox.Lang;
import Toybox.Math;
import Toybox.Time;
import Toybox.WatchUi;

class KumaView extends WatchUi.View {

    // List area, as fractions of the screen height. Kept symmetric around the centre so the
    // inscribed box is as wide as possible on the round screen.
    private const LIST_TOP = 0.23;
    private const LIST_BOTTOM = 0.77;
    private const MARGIN = 10;
    private const DOT_R = 9;

    private var _monitors as Array<Array>? = null;
    private var _down as Number = 0;
    private var _total as Number = 0;
    private var _updatedAt as Number? = null;
    private var _loading as Boolean = false;
    private var _error as Number? = null;
    private var _offset as Number = 0;
    private var _visibleRows as Number = 1;

    function initialize() {
        View.initialize();
    }

    function onShow() as Void {
        refresh();
    }

    function refresh() as Void {
        if (_loading) {
            return;
        }
        _error = Kuma.preflight();
        if (_error == null) {
            _loading = true;
            Kuma.request(method(:onResponse));
        }
        WatchUi.requestUpdate();
    }

    function onResponse(responseCode as Number, data as Dictionary or String or Null) as Void {
        _loading = false;
        if (responseCode == 200 && data instanceof Dictionary && Kuma.isValid(data)) {
            _monitors = data["h"] as Array<Array>;
            _down = data["d"] as Number;
            _total = data["t"] as Number;
            var summary = Kuma.summarize(data);
            _updatedAt = summary["ts"] as Number;
            _offset = clampOffset(_offset);
            Application.Storage.setValue(Kuma.STORAGE_SUMMARY, summary as Application.Storage.ValueType);
        } else {
            _error = responseCode == 200 ? Kuma.ERR_BAD_RESPONSE : responseCode;
        }
        WatchUi.requestUpdate();
    }

    // Scrolls by one page (minus one row, to keep context); returns false at the ends.
    function scroll(direction as Number) as Boolean {
        if (_monitors == null) {
            return false;
        }
        var step = _visibleRows > 1 ? _visibleRows - 1 : 1;
        var offset = clampOffset(_offset + direction * step);
        if (offset == _offset) {
            return false;
        }
        _offset = offset;
        WatchUi.requestUpdate();
        return true;
    }

    function onUpdate(dc as Graphics.Dc) as Void {
        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
        dc.clear();
        var cx = dc.getWidth() / 2;
        var h = dc.getHeight();

        if (_monitors == null) {
            if (_error != null) {
                drawError(dc, cx, h);
            } else {
                drawCentered(dc, cx, h / 2, Graphics.FONT_MEDIUM, Graphics.COLOR_LT_GRAY, text(Rez.Strings.Loading));
            }
            return;
        }

        drawHeader(dc, cx, h);
        drawList(dc, cx, h);
        drawFooter(dc, cx, h);
    }

    private function drawHeader(dc as Graphics.Dc, cx as Number, h as Number) as Void {
        var monitors = _monitors as Array<Array>;
        var up = 0;
        for (var i = 0; i < monitors.size(); i++) {
            if (monitors[i][1] == Kuma.UP) {
                up++;
            }
        }
        var color = _down > 0 ? Graphics.COLOR_RED : (up == _total ? Graphics.COLOR_GREEN : Graphics.COLOR_ORANGE);
        drawCentered(dc, cx, (h * 0.13).toNumber(), Graphics.FONT_MEDIUM, color, up + "/" + _total + " up");
    }

    private function drawList(dc as Graphics.Dc, cx as Number, h as Number) as Void {
        var monitors = _monitors as Array<Array>;
        if (monitors.size() == 0) {
            drawCentered(dc, cx, h / 2, Graphics.FONT_SMALL, Graphics.COLOR_LT_GRAY, text(Rez.Strings.NoMonitors));
            return;
        }

        var font = Graphics.FONT_SMALL;
        var rowH = Graphics.getFontHeight(font) + 6;
        var top = (h * LIST_TOP).toNumber();
        var bottom = (h * LIST_BOTTOM).toNumber();
        _visibleRows = (bottom - top) / rowH;
        top += (bottom - top - _visibleRows * rowH) / 2;

        // Widest box that fits in the circle between top and bottom.
        var r = h / 2;
        var dy = (r - top) > (top + _visibleRows * rowH - r) ? r - top : top + _visibleRows * rowH - r;
        var half = Math.sqrt(r * r - dy * dy).toNumber() - MARGIN;
        var dotX = cx - half + DOT_R;
        var textX = dotX + DOT_R + 10;
        var textW = cx + half - textX;

        for (var i = 0; i < _visibleRows && _offset + i < monitors.size(); i++) {
            var item = monitors[_offset + i];
            var y = top + i * rowH + rowH / 2;
            dc.setColor(statusColor(item[1] as Number), Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(dotX, y, DOT_R);
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
            dc.drawText(textX, y, font, fit(dc, item[0] as String, font, textW),
                Graphics.TEXT_JUSTIFY_LEFT | Graphics.TEXT_JUSTIFY_VCENTER);
        }

        if (monitors.size() > _visibleRows) {
            drawScrollbar(dc, cx, h, monitors.size());
        }
    }

    // Arc along the right edge, between 2 o'clock and 4 o'clock.
    private function drawScrollbar(dc as Graphics.Dc, cx as Number, h as Number, count as Number) as Void {
        var span = 60.0;
        var r = h / 2 - 5;
        dc.setPenWidth(4);
        dc.setColor(Graphics.COLOR_DK_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawArc(cx, h / 2, r, Graphics.ARC_CLOCKWISE, 30, 330);
        var start = 30 - span * _offset / count;
        var length = span * _visibleRows / count;
        dc.setColor(Graphics.COLOR_LT_GRAY, Graphics.COLOR_TRANSPARENT);
        dc.drawArc(cx, h / 2, r, Graphics.ARC_CLOCKWISE, start.toNumber(), (start - length).toNumber());
        dc.setPenWidth(1);
    }

    private function drawFooter(dc as Graphics.Dc, cx as Number, h as Number) as Void {
        var y = (h * 0.86).toNumber();
        if (_loading) {
            drawCentered(dc, cx, y, Graphics.FONT_XTINY, Graphics.COLOR_LT_GRAY, text(Rez.Strings.Updating));
        } else if (_error != null) {
            drawCentered(dc, cx, y, Graphics.FONT_XTINY, Graphics.COLOR_RED, errorText(_error));
        } else if (_updatedAt != null) {
            drawCentered(dc, cx, y, Graphics.FONT_XTINY, Graphics.COLOR_LT_GRAY, Lang.format(text(Rez.Strings.UpdatedAt), [Kuma.formatTime(_updatedAt)]));
        }
    }

    private function drawError(dc as Graphics.Dc, cx as Number, h as Number) as Void {
        var r = 22;
        dc.setColor(Graphics.COLOR_RED, Graphics.COLOR_TRANSPARENT);
        KumaIcons.drawWarning(dc, cx, (h * 0.28).toNumber(), r);
        drawCentered(dc, cx, h / 2, Graphics.FONT_SMALL, Graphics.COLOR_WHITE, errorText(_error));
        drawCentered(dc, cx, (h * 0.72).toNumber(), Graphics.FONT_XTINY, Graphics.COLOR_LT_GRAY, text(Rez.Strings.TapToRetry));
    }

    private function drawCentered(dc as Graphics.Dc, x as Number, y as Number, font as Graphics.FontType,
            color as Graphics.ColorType, text as String) as Void {
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, y, font, text, Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
    }

    private function clampOffset(offset as Number) as Number {
        var max = _monitors == null ? 0 : (_monitors as Array).size() - _visibleRows;
        if (offset > max) {
            offset = max;
        }
        return offset < 0 ? 0 : offset;
    }

    private function fit(dc as Graphics.Dc, text as String, font as Graphics.FontType, maxWidth as Number) as String {
        if (dc.getTextWidthInPixels(text, font) <= maxWidth) {
            return text;
        }
        while (text.length() > 1 && dc.getTextWidthInPixels(text + "…", font) > maxWidth) {
            text = text.substring(0, text.length() - 1) as String;
        }
        return text + "…";
    }

    private function text(id as ResourceId) as String {
        return WatchUi.loadResource(id) as String;
    }

    private function statusColor(status as Number) as Graphics.ColorType {
        if (status == Kuma.DOWN) {
            return Graphics.COLOR_RED;
        } else if (status == Kuma.PENDING) {
            return Graphics.COLOR_ORANGE;
        } else if (status == Kuma.MAINTENANCE) {
            return Graphics.COLOR_BLUE;
        }
        return Graphics.COLOR_GREEN;
    }

    private function errorText(code as Number?) as String {
        if (code == Kuma.ERR_NOT_CONFIGURED) {
            return text(Rez.Strings.ErrNotConfigured);
        } else if (code == Kuma.ERR_NO_PHONE || code == Communications.BLE_CONNECTION_UNAVAILABLE) {
            return text(Rez.Strings.ErrNoPhone);
        } else if (code == Communications.NETWORK_REQUEST_TIMED_OUT || code == Communications.BLE_HOST_TIMEOUT) {
            return text(Rez.Strings.ErrTimeout);
        } else if (code == Communications.SECURE_CONNECTION_REQUIRED) {
            return text(Rez.Strings.ErrHttps);
        } else if (code == 401) {
            return text(Rez.Strings.ErrToken);
        } else if (code == 502) {
            return text(Rez.Strings.ErrKuma);
        } else if (code == Kuma.ERR_BAD_RESPONSE || code == Communications.INVALID_HTTP_BODY_IN_NETWORK_RESPONSE) {
            return text(Rez.Strings.ErrBadResponse);
        } else if (code == Communications.NETWORK_RESPONSE_TOO_LARGE || code == Communications.NETWORK_RESPONSE_OUT_OF_MEMORY) {
            return text(Rez.Strings.ErrTooLarge);
        }
        return Lang.format(text(Rez.Strings.ErrOther), [code]);
    }
}
