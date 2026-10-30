import Toybox.Lang;
import Toybox.WatchUi;

class KumaDelegate extends WatchUi.BehaviorDelegate {

    private var _view as KumaView;

    function initialize(view as KumaView) {
        BehaviorDelegate.initialize();
        _view = view;
    }

    // Tap or top-right (action) button.
    function onSelect() as Boolean {
        _view.onTap();
        return true;
    }

    // Swipe up / down (no up/down buttons on the vivoactive 6).
    function onNextPage() as Boolean {
        return _view.scroll(1);
    }

    function onPreviousPage() as Boolean {
        return _view.scroll(-1);
    }
}
