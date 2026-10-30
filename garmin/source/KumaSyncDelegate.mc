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

    // Only syncs the user asked for: a sync the system starts by itself while charging can
    // block charging (known Connect IQ issue).
    function isSyncNeeded() as Boolean {
        return Application.Storage.getValue(Kuma.STORAGE_SYNC_REQUESTED) == true;
    }

    function onStartSync() as Void {
        if (Kuma.preflight() == Kuma.ERR_NOT_CONFIGURED) {
            finish(WatchUi.loadResource(Rez.Strings.ErrNotConfigured) as String);
            return;
        }
        Kuma.request(false, method(:onResponse));
    }

    function onStopSync() as Void {
        Communications.cancelAllRequests();
        finish(null);
    }

    // The full payload is cached for the app to show on its next launch.
    function onResponse(responseCode as Number, data as Dictionary or String or Null) as Void {
        if (responseCode == 200 && data instanceof Dictionary && Kuma.isValid(data)) {
            Kuma.cache(data);
            finish(null);
        } else {
            finish("HTTP " + responseCode);
        }
    }

    private function finish(errorMessage as String?) as Void {
        Application.Storage.deleteValue(Kuma.STORAGE_SYNC_REQUESTED);
        Communications.notifySyncComplete(errorMessage);
    }
}
