import XCTest

final class CasgrainSmokeUITests: XCTestCase {
    private let appBundleIdentifier = "org.casgrain.fixtures.CasgrainSmoke"

    func testTapChangesVisibleStateAndCapturesScreenshot() {
        let app = XCUIApplication(bundleIdentifier: appBundleIdentifier)
        app.launch()

        let statusLabel = app.staticTexts["status-label"]
        XCTAssertTrue(statusLabel.waitForExistence(timeout: 10))

        let countLabel = app.staticTexts["count-label"]
        let tapButton = app.buttons["tap-button"]
        XCTAssertTrue(tapButton.waitForExistence(timeout: 10))
        XCTAssertEqual(countLabel.label, "Count: 0")

        tapButton.tap()
        XCTAssertEqual(countLabel.label, "Count: 1")

        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = "CasgrainSmoke-count-1"
        attachment.lifetime = .keepAlways
        add(attachment)

        if let screenshotPath = ProcessInfo.processInfo.environment["CASGRAIN_SMOKE_SCREENSHOT_PATH"],
           !screenshotPath.isEmpty {
            let destinationURL = URL(fileURLWithPath: screenshotPath)
            try? FileManager.default.createDirectory(
                at: destinationURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            try? screenshot.pngRepresentation.write(to: destinationURL)
        }
    }
}
