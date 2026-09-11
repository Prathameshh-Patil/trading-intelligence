//! Where the window was, per monitor arrangement — and why it is not just (x, y).
//!
//! `phase-2-month-one.md` W2D1 asks for *"position memory means the window
//! reopens where the trader left it, per monitor, surviving a monitor being
//! unplugged."* Three clauses, and the last two are the work.
//!
//! **A saved (x, y) alone is a bug waiting for a docking station.** Restore it
//! after the second monitor is gone and the window opens at coordinates no
//! display covers — invisible, still running, still always-on-top, with no
//! title bar to find it by because `decorations` is `false`. The trader's only
//! recourse is deleting a config file they do not know exists.
//!
//! So placements are keyed by a **signature of the whole arrangement**: every
//! connected monitor's origin and size. A desk with two screens and a laptop on
//! a train are different keys, which is what "per monitor" buys — each layout
//! remembers its own spot instead of the last one overwriting the other.
//!
//! And a key match is still not trusted on its own. A resolution change leaves
//! the signature intact while moving the usable area, so a restored placement
//! is checked against the monitors that exist *now* and discarded if too little
//! of it would be reachable.

use std::collections::HashMap;
use std::path::Path;

use serde::{Deserialize, Serialize};

/// A window or monitor rectangle, in physical pixels on the virtual desktop.
#[derive(Serialize, Deserialize, Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

impl Rect {
    fn right(&self) -> i32 {
        self.x + self.width as i32
    }
    fn bottom(&self) -> i32 {
        self.y + self.height as i32
    }

    /// Area of the overlap with `other`, in pixels. Zero when they do not touch.
    fn overlap(&self, other: &Rect) -> u64 {
        let w = (self.right().min(other.right()) - self.x.max(other.x)).max(0) as u64;
        let h = (self.bottom().min(other.bottom()) - self.y.max(other.y)).max(0) as u64;
        w * h
    }
}

/// How much of the window must land on a real display for a restore to be used.
///
/// **Not one pixel.** A sliver on the edge is technically visible and useless:
/// `decorations` is `false`, so the only way to move this window is the topbar
/// drag region, and a trader who cannot reach the topbar cannot recover it.
/// 160x48 is a conservative grab area — comfortably larger than the drag
/// region's height, small enough that a deliberately half-offscreen window is
/// still honoured.
pub const MIN_VISIBLE_W: u32 = 160;
pub const MIN_VISIBLE_H: u32 = 48;

/// A stable key for one monitor arrangement.
///
/// Sorted, so the same displays enumerated in a different order by the OS
/// produce the same key — otherwise a reboot could silently orphan a placement
/// and look like the feature had simply forgotten.
pub fn signature(monitors: &[Rect]) -> String {
    let mut parts: Vec<String> = monitors
        .iter()
        .map(|m| format!("{}x{}@{},{}", m.width, m.height, m.x, m.y))
        .collect();
    parts.sort();
    parts.join("|")
}

/// Is enough of `placement` on a real display to be reachable?
pub fn is_reachable(placement: &Rect, monitors: &[Rect]) -> bool {
    let need = (MIN_VISIBLE_W as u64) * (MIN_VISIBLE_H as u64);
    monitors.iter().any(|m| {
        let w = (placement.right().min(m.right()) - placement.x.max(m.x)).max(0) as u32;
        let h = (placement.bottom().min(m.bottom()) - placement.y.max(m.y)).max(0) as u32;
        // Both dimensions must clear the minimum, not just the product -- a
        // 2000x1 strip has ample area and nothing to grab.
        w >= MIN_VISIBLE_W && h >= MIN_VISIBLE_H && placement.overlap(m) >= need
    })
}

/// Every remembered placement, keyed by arrangement signature.
#[derive(Serialize, Deserialize, Default, Debug, Clone)]
pub struct Placements(HashMap<String, Rect>);

impl Placements {
    /// The placement to open at, or `None` to let the window use its configured
    /// default.
    ///
    /// `None` is returned for two different reasons and the caller must not
    /// distinguish them: this arrangement has never been seen, or what was
    /// saved for it would no longer be reachable. Both mean "open where
    /// `tauri.conf.json` says", which is always on a display that exists.
    pub fn restore(&self, monitors: &[Rect]) -> Option<Rect> {
        let saved = self.0.get(&signature(monitors))?;
        is_reachable(saved, monitors).then_some(*saved)
    }

    /// Remember `placement` for the arrangement currently connected.
    ///
    /// An unreachable placement is **not** stored. Saving one would mean
    /// restoring it later, and the restore-side check would then be the only
    /// thing between the trader and an invisible window.
    pub fn remember(&mut self, monitors: &[Rect], placement: Rect) {
        if is_reachable(&placement, monitors) {
            self.0.insert(signature(monitors), placement);
        }
    }

    pub fn load(path: &Path) -> Self {
        std::fs::read_to_string(path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            // A missing or corrupt file is an empty memory, never an error. The
            // window opening at its default is a worse outcome than a crash for
            // exactly nobody.
            .unwrap_or_default()
    }

    pub fn save(&self, path: &Path) -> std::io::Result<()> {
        if let Some(dir) = path.parent() {
            std::fs::create_dir_all(dir)?;
        }
        std::fs::write(path, serde_json::to_string_pretty(self)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const LAPTOP: Rect = Rect { x: 0, y: 0, width: 1728, height: 1117 };
    const EXTERNAL: Rect = Rect { x: 1728, y: 0, width: 2560, height: 1440 };
    const WINDOW: Rect = Rect { x: 100, y: 100, width: 380, height: 820 };

    #[test]
    fn signature_is_stable_across_enumeration_order() {
        assert_eq!(signature(&[LAPTOP, EXTERNAL]), signature(&[EXTERNAL, LAPTOP]));
    }

    #[test]
    fn unplugging_a_monitor_changes_the_signature() {
        assert_ne!(signature(&[LAPTOP, EXTERNAL]), signature(&[LAPTOP]));
    }

    #[test]
    fn each_arrangement_remembers_its_own_spot() {
        let desk = [LAPTOP, EXTERNAL];
        let train = [LAPTOP];
        let on_external = Rect { x: 2000, y: 200, width: 380, height: 820 };

        let mut p = Placements::default();
        p.remember(&desk, on_external);
        p.remember(&train, WINDOW);

        assert_eq!(p.restore(&desk), Some(on_external));
        assert_eq!(p.restore(&train), Some(WINDOW));
    }

    #[test]
    fn a_placement_on_a_now_unplugged_monitor_is_not_restored() {
        // The whole point of W2D1's third clause. Saved on the external, then
        // the dock is unplugged: the signature no longer matches, and even if
        // it did the rectangle is nowhere.
        let mut p = Placements::default();
        p.remember(&[LAPTOP, EXTERNAL], Rect { x: 2600, y: 300, width: 380, height: 820 });
        assert_eq!(p.restore(&[LAPTOP]), None);
    }

    #[test]
    fn a_saved_placement_is_rechecked_against_the_monitors_that_exist_now() {
        // Signature unchanged is NOT enough: a placement can be saved and the
        // display later shrink beneath it.
        let big = [Rect { x: 0, y: 0, width: 3840, height: 2160 }];
        let mut p = Placements::default();
        p.remember(&big, Rect { x: 3000, y: 1800, width: 380, height: 820 });
        // Same key, smaller monitor -- hand-built to isolate the reachability check.
        let shrunk = [Rect { x: 0, y: 0, width: 1280, height: 800 }];
        assert!(!is_reachable(&Rect { x: 3000, y: 1800, width: 380, height: 820 }, &shrunk));
    }

    #[test]
    fn a_sliver_on_screen_is_not_reachable() {
        // 20px of a 380px window showing. Technically visible; there is no
        // title bar, so there is nothing to grab.
        let sliver = Rect { x: LAPTOP.right() - 20, y: 100, width: 380, height: 820 };
        assert!(!is_reachable(&sliver, &[LAPTOP]));
    }

    #[test]
    fn a_wide_but_flat_overlap_is_not_reachable() {
        // Ample AREA, no grabbable height -- the reason the check is per
        // dimension and not on the product alone.
        let flat = Rect { x: 0, y: LAPTOP.bottom() - 10, width: 380, height: 820 };
        assert!(!is_reachable(&flat, &[LAPTOP]));
    }

    #[test]
    fn a_deliberately_half_offscreen_window_is_still_honoured() {
        let half = Rect { x: LAPTOP.right() - 200, y: 100, width: 380, height: 820 };
        assert!(is_reachable(&half, &[LAPTOP]));
    }

    // `remember` refuses to store an unreachable placement AND `restore`
    // rechecks one. That is deliberate -- either alone would be enough today,
    // and the pair survives one of them being edited out. But it also means a
    // test that goes in through `remember` and out through `restore` passes
    // with either guard deleted, so each is exercised on its own below.
    // Both mutations survived until these two existed.

    #[test]
    fn remember_does_not_store_an_unreachable_placement() {
        let mut p = Placements::default();
        p.remember(&[LAPTOP], Rect { x: 9000, y: 9000, width: 380, height: 820 });
        // Through the serialised form, so this does not depend on `restore`.
        assert_eq!(serde_json::to_string(&p).unwrap(), "{}");
    }

    #[test]
    fn restore_rejects_an_unreachable_placement_it_finds_on_disk() {
        // Built by deserialising rather than by `remember`, so the store-side
        // guard cannot be what makes this pass. A file written by an older
        // build, or hand-edited, reaches exactly this state.
        let key = signature(&[LAPTOP]);
        let json = format!(
            r#"{{"{key}":{{"x":9000,"y":9000,"width":380,"height":820}}}}"#
        );
        let p: Placements = serde_json::from_str(&json).unwrap();
        assert_eq!(p.restore(&[LAPTOP]), None);
    }

    #[test]
    fn a_missing_file_is_an_empty_memory_not_an_error() {
        let p = Placements::load(Path::new("/nonexistent/placements.json"));
        assert_eq!(p.restore(&[LAPTOP]), None);
    }

    #[test]
    fn a_corrupt_file_is_an_empty_memory_not_an_error() {
        let dir = std::env::temp_dir().join("ti_placement_corrupt");
        std::fs::create_dir_all(&dir).unwrap();
        let f = dir.join("placements.json");
        std::fs::write(&f, "{ not json").unwrap();
        assert_eq!(Placements::load(&f).restore(&[LAPTOP]), None);
    }

    #[test]
    fn it_round_trips_through_disk() {
        let dir = std::env::temp_dir().join("ti_placement_roundtrip");
        let f = dir.join("placements.json");
        let _ = std::fs::remove_file(&f);

        let mut p = Placements::default();
        p.remember(&[LAPTOP], WINDOW);
        p.save(&f).unwrap();

        assert_eq!(Placements::load(&f).restore(&[LAPTOP]), Some(WINDOW));
    }
}
