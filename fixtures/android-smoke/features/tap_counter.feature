Feature: Android smoke tap counter
  Scenario: Increment the counter once
    Given the app is launched
    When the user taps tap button
    Then count label text is "Count: 1"
    When the user takes a screenshot
