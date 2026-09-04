import CoreGraphics
import Foundation

let options: CGWindowListOption = [.optionOnScreenOnly, .excludeDesktopElements]
guard let windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID)
    as? [[String: Any]]
else {
    exit(1)
}

for window in windows {
    let owner = window[kCGWindowOwnerName as String] as? String
    let title = window[kCGWindowName as String] as? String
    let number = window[kCGWindowNumber as String] as? Int
    if owner?.localizedCaseInsensitiveContains("Ghostty") == true,
       title == "BuddyMon Menu",
       let number {
        print(number)
        exit(0)
    }
}

exit(1)
