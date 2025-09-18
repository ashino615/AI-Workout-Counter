package arai.sakura.aiworkout.utils

import android.content.Context
import android.os.Build
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import java.util.Locale
import java.util.UUID
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * Text-to-Speech helper that handles async initialization and provides
 * convenient methods for speech synthesis with customizable parameters.
 *
 * Key features:
 * - Automatic queuing of speak requests during initialization
 * - Configurable language, rate, and pitch settings
 * - Per-request parameter overrides
 * - Thread-safe operation
 */
class TTSHelper(
    context: Context,
    private var locale: Locale = Locale.ENGLISH,
    private var defaultRate: Float = 1.5f,   // Range: 0.1f - 2.0f
    private var defaultPitch: Float = 1.0f   // Range: 0.5f - 2.0f
) {


    private val appContext = context.applicationContext
    private val pending = ConcurrentLinkedQueue<TtsItem>()
    private var ready = false

    private val tts: TextToSpeech = TextToSpeech(appContext) { status ->
        ready = (status == TextToSpeech.SUCCESS) && setLanguage(locale)
        if (ready) {
            tts.setSpeechRate(defaultRate)
            tts.setPitch(defaultPitch)
            // Process any queued speech requests from before initialization
            drainQueue()
        }
    }.apply {
        setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) {}
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) {}
            override fun onError(utteranceId: String?, errorCode: Int) {}
        })
    }

    /**
     * Sets the language for text-to-speech output
     * @return true if language was successfully set, false if not supported
     */
    fun setLanguage(newLocale: Locale): Boolean {
        locale = newLocale
        val result = tts.setLanguage(newLocale)
        return result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED
    }

    /**
     * Updates default speech parameters for future speak() calls
     */
    fun configure(rate: Float = defaultRate, pitch: Float = defaultPitch) {
        defaultRate = rate
        defaultPitch = pitch
        if (ready) {
            tts.setSpeechRate(defaultRate)
            tts.setPitch(defaultPitch)
        }
    }

    /**
     * Speaks the given text with optional parameter overrides
     *
     * @param text Text to speak
     * @param flush If true, stops current speech and replaces with this text
     * @param rate Speech rate override (null to use default)
     * @param pitch Speech pitch override (null to use default)
     * @return Unique utterance ID for tracking (can be ignored if not needed)
     */
    fun speak(
        text: String,
        flush: Boolean = false,
        rate: Float? = null,
        pitch: Float? = null
    ): String {
        val id = UUID.randomUUID().toString()
        val item = TtsItem(id, text, flush, rate, pitch)

        if (!ready) {
            pending.add(item)
            return id
        }

        // Apply temporary parameter overrides
        val oldRate = tts.voiceRateCompat()
        val oldPitch = tts.voicePitchCompat()

        if (rate != null) tts.setSpeechRate(rate)
        if (pitch != null) tts.setPitch(pitch)

        val mode = if (flush) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
        speakInternal(item, mode)

        // Restore original parameters
        if (rate != null) tts.setSpeechRate(oldRate)
        if (pitch != null) tts.setPitch(oldPitch)
        return id
    }

    /**
     * Stops all current speech output (preserves queue)
     */
    fun stop() {
        runCatching { tts.stop() }
    }

    /**
     * Completely shuts down TTS engine and clears all queued items.
     * Call this in Activity/Fragment onDestroy()
     */
    fun shutdown() {
        runCatching { tts.stop() }
        runCatching { tts.shutdown() }
        pending.clear()
        ready = false
    }

    /**
     * @return true if TTS engine is initialized and ready for use
     */
    val isReady: Boolean get() = ready

    // Private implementation methods

    private fun drainQueue() {
        var first = true
        while (true) {
            val item = pending.poll() ?: break
            val mode = if (first && item.flush) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD
            first = false

            // Apply individual parameter overrides if specified
            val oldRate = tts.voiceRateCompat()
            val oldPitch = tts.voicePitchCompat()
            if (item.rate != null) tts.setSpeechRate(item.rate)
            if (item.pitch != null) tts.setPitch(item.pitch)
            speakInternal(item, mode)
            if (item.rate != null) tts.setSpeechRate(oldRate)
            if (item.pitch != null) tts.setPitch(oldPitch)
        }
    }

    private fun speakInternal(item: TtsItem, mode: Int) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            tts.speak(item.text, mode, null, item.id)
        } else {
            @Suppress("DEPRECATION")
            tts.speak(item.text, mode, hashMapOf(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID to item.id))
        }
    }

    private data class TtsItem(
        val id: String,
        val text: String,
        val flush: Boolean,
        val rate: Float?,
        val pitch: Float?
    )

    // Compatibility methods for accessing TTS parameters
    // Note: TTS doesn't expose getters for rate/pitch, so we maintain our own state
    private fun TextToSpeech.voiceRateCompat(): Float = try {
        defaultRate
    } catch (_: Throwable) { defaultRate }

    private fun TextToSpeech.voicePitchCompat(): Float = try {
        defaultPitch
    } catch (_: Throwable) { defaultPitch }
}