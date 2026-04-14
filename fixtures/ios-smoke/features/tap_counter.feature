Feature: iOS smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then "Count: 1" is displayed
    When the user takes a screenshot
