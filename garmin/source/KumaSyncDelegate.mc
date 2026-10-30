import Toybox.Application;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.WatchUi;

// Runs when the app is relaunched in sync mode (Communications.startSync2). Requests made
// here can go over Wi-Fi, so this is how the watch refreshes without the phone.
class KumaSyncDelegate extends Communications.SyncDelegate {

    function initialize() {
        SyncDelegate.initialize();
    }

    function isSyncNeeded() as Boolean {
        return true;
    }

    function onStartSync() as Void {
        if (Kuma.preflight() == Kuma.ERR_NOT_CONFIGURED) {
            Communications.notifySyncComplete(WatchUi.loadResource(Rez.Strings.ErrNotConfigured) as String);
            return;
        }
        Kuma.request(false, method(:onResponse));
    }

    function onStopSync() as Void {
        Communications.cancelAllRequests();
        Communications.notifySyncComplete(null);
    }

    // The full payload is cached for the app to show on its next launch.
    function onResponse(responseCode as Number, data as Dictionary or String or Null) as Void {
        if (responseCode == 200 && data instanceof Dictionary && Kuma.isValid(data)) {
            Kuma.cache(data);
            Communications.notifySyncComplete(null);
        } else {
            Communications.notifySyncComplete("HTTP " + responseCode);
        }
    }
}
