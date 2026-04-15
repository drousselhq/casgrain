package hq.droussel.casgrain.smoke

import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity

class MainActivity : AppCompatActivity() {
    private var tapCount: Int = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        val countLabel = findViewById<TextView>(R.id.count_label)
        val tapButton = findViewById<Button>(R.id.tap_button)

        fun renderCount() {
            countLabel.text = getString(R.string.count_label_text, tapCount)
        }

        renderCount()
        tapButton.setOnClickListener {
            tapCount += 1
            renderCount()
        }
    }
}
