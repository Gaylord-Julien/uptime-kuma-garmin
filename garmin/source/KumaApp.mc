import Toybox.Application;
import Toybox.Background;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.WatchUi;

(:background)
class KumaApp extends Application.AppBase {

    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() as [WatchUi.Views] or [WatchUi.Views, WatchUi.InputDelegates] {
        registerBackground();
        var view = new KumaView();
        return [view, new KumaDelegate(view)];
    }

    (:glance)
    function getGlanceView() as [WatchUi.GlanceView] or [WatchUi.GlanceView, WatchUi.GlanceViewDelegate] or Null {
        registerBackground();
        return [new KumaGlanceView()];
    }

    function getServiceDelegate() as [System.ServiceDelegate] {
        return [new KumaServiceDelegate()];
    }

    function getSyncDelegate() as Communications.SyncDelegate? {
        return new KumaSyncDelegate();
    }

    // Runs in the foreground (app or glance) with what the service passed to Background.exit().
    function onBackgroundData(data as Application.PersistableType) as Void {
        if (data instanceof Dictionary) {
            Application.Storage.setValue(Kuma.STORAGE_SUMMARY, data as Application.Storage.ValueType);
            WatchUi.requestUpdate();
        }
    }

    function onSettingsChanged() as Void {
        registerBackground();
        WatchUi.requestUpdate();
    }

    (:glance)
    private function registerBackground() as Void {
        // Re-registered when the interval setting changed.
        var period = Kuma.backgroundPeriod();
        var registered = Background.getTemporalEventRegisteredTime();
        if (!(registered instanceof Time.Duration) || registered.value() != period) {
            Background.registerForTemporalEvent(new Time.Duration(period));
        }
    }
}
