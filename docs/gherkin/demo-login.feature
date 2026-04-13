Feature: Login
  Scenario: Successful login
    Given the app is launched
    When the user enters "daniel@example.com" into email field
    When the user taps login button
    When the user takes a screenshot
    Then Home is visible
