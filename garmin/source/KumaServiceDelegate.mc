import Toybox.Background;
import Toybox.Lang;
import Toybox.System;

// Refreshes the glance summary every Kuma.backgroundPeriod() seconds.
(:background)
class KumaServiceDelegate extends System.ServiceDelegate {

    function initialize() {
        ServiceDelegate.initialize();
    }

    function onTemporalEvent() as Void {
        if (Kuma.preflight() != null) {
            Background.exit(null);
            return;
        }
        Kuma.request(true, method(:onResponse));
    }

    // Only the summary is passed back: the glance doesn't need the monitor list.
    function onResponse(responseCode as Number, data as Dictionary or String or Null) as Void {
        if (responseCode == 200 && data instanceof Dictionary && Kuma.isSummary(data)) {
            Background.exit(Kuma.summarize(data));
        } else {
            Background.exit(null);
        }
    }
}
