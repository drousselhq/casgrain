import XCTest

final class CasgrainSmokeUITests: XCTestCase {
    func testTapChangesVisibleStateAndCapturesScreenshot() {
        let app = XCUIApplication()
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
    }
}
