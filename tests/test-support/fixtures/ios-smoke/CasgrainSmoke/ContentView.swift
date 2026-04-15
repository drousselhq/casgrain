import SwiftUI

struct ContentView: View {
    @State private var tapCount = 0

    var body: some View {
        VStack(spacing: 16) {
            Text("Casgrain smoke ready")
                .font(.headline)
                .accessibilityIdentifier("status-label")

            Text("Count: \(tapCount)")
                .font(.title2)
                .accessibilityIdentifier("count-label")

            Button("Tap once") {
                tapCount += 1
            }
            .buttonStyle(.borderedProminent)
            .accessibilityIdentifier("tap-button")
        }
        .padding()
    }
}
