import Toybox.Application;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;

// Shared by the app, the glance and the background service: keep it small.
(:background, :glance)
module Kuma {
    // Last known summary {"d" => down, "t" => total, "ts" => epoch seconds}, read by the glance.
    const STORAGE_SUMMARY = "s";
    // Last full payload from the proxy plus "ts", shown by the app when it can't refresh.
    const STORAGE_FULL = "f";
    // Set when the user asks for a Wi-Fi sync, so the system can't start one on its own.
    const STORAGE_SYNC_REQUESTED = "r";
    // Background temporal events can't fire more often than every 5 minutes.
    const BACKGROUND_PERIOD = 5 * 60;

    // Monitor states, as sent by the proxy.
    const DOWN = 0;
    const UP = 1;
    const PENDING = 2;
    const MAINTENANCE = 3;

    // Local errors; other negative codes come from Communications, positive ones are HTTP statuses.
    const ERR_NOT_CONFIGURED = -9001;
    const ERR_NO_PHONE = -9002;
    const ERR_BAD_RESPONSE = -9003;
    const ERR_NO_WIFI = -9004;

    // Returns an error code if a request can't be sent right now, null otherwise.
    function preflight() as Number? {
        if (getSetting("proxyUrl").length() == 0 || getSetting("proxyToken").length() == 0) {
            return ERR_NOT_CONFIGURED;
        }
        if (!System.getDeviceSettings().phoneConnected) {
            return ERR_NO_PHONE;
        }
        return null;
    }

    // summary: counts only, without the monitor list (the background service has 64 KB of memory).
    // A proxy that predates ?summary=1 ignores it and sends the full payload, which still works.
    function request(summary as Boolean, callback as Method(responseCode as Number, data as Dictionary or String or Null) as Void) as Void {
        var url = getSetting("proxyUrl");
        if (summary) {
            url += (url.find("?") == null ? "?" : "&") + "summary=1";
        }
        Communications.makeWebRequest(url, null, {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :headers => { "Authorization" => "Bearer " + getSetting("proxyToken") },
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        }, callback);
    }

    function isValid(data as Dictionary) as Boolean {
        if (isSummary(data) && data["h"] instanceof Array) {
            return true;
        }
        return false;
    }

    function isSummary(data as Dictionary) as Boolean {
        if (data["d"] instanceof Number && data["t"] instanceof Number) {
            return true;
        }
        return false;
    }

    function summarize(data as Dictionary) as Dictionary<Application.PropertyKeyType, Application.PropertyValueType> {
        return { "d" => data["d"] as Number, "t" => data["t"] as Number, "ts" => Time.now().value() };
    }

    // Called by the app and the sync delegate, never by the background service (which only
    // fetches the summary).
    function cache(data as Dictionary) as Void {
        var summary = summarize(data);
        data["ts"] = summary["ts"];
        Application.Storage.setValue(STORAGE_FULL, data as Application.Storage.ValueType);
        Application.Storage.setValue(STORAGE_SUMMARY, summary as Application.Storage.ValueType);
    }

    // "14:32" (or "2:32 pm" on a 12-hour watch) today, "24 Oct" if older than a day
    // (month name in the device language).
    function formatTime(ts as Number) as String {
        var info = Gregorian.info(new Time.Moment(ts), Time.FORMAT_MEDIUM);
        if (Time.now().value() - ts > Gregorian.SECONDS_PER_DAY) {
            return info.day + " " + info.month;
        }
        var min = info.min.format("%02d");
        if (System.getDeviceSettings().is24Hour) {
            return info.hour.format("%02d") + ":" + min;
        }
        var hour = info.hour % 12 == 0 ? 12 : info.hour % 12;
        return hour + ":" + min + (info.hour < 12 ? " am" : " pm");
    }

    function getSetting(key as String) as String {
        var value = Application.Properties.getValue(key);
        return value instanceof String ? value : "";
    }
}
