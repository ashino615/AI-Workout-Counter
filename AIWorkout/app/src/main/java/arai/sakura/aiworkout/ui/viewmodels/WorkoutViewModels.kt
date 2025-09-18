package arai.sakura.aiworkout.ui.viewmodels

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import arai.sakura.aiworkout.ui.components.ConnectionStatus
import arai.sakura.aiworkout.ui.screens.WorkoutUiState
import arai.sakura.aiworkout.utils.ApiService
import arai.sakura.aiworkout.utils.TTSHelper
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex

/**
 * ViewModel managing workout session state, server communication, and TTS feedback.
 *
 * Responsibilities:
 * - Exercise type selection and workout session control
 * - Frame processing and rep counting via API
 * - Connection health monitoring with automatic retry
 * - Text-to-speech feedback coordination
 */
class WorkoutViewModel(
    private val api: ApiService,
    private val tts: TTSHelper? = null,
    private val io: CoroutineDispatcher = Dispatchers.IO
) : ViewModel() {

    // Exercise type initialization methods
    fun startPushUp() {
        dispatch(WorkoutAction.SetExerciseMode("pushup"))
        start()
    }

    fun startPullUp() {
        dispatch(WorkoutAction.SetExerciseMode("chinup"))
        start()
    }

    fun startSquat() {
        dispatch(WorkoutAction.SetExerciseMode("squat"))
        start()
    }

    fun startArmCurl() {
        dispatch(WorkoutAction.SetExerciseMode("armcurl"))
        start()
    }

    private val _state = MutableStateFlow(WorkoutState())

    val uiState: StateFlow<WorkoutUiState> =
        _state
            .map { it.toUiState() }
            .stateIn(
                scope = viewModelScope,
                started = SharingStarted.Eagerly,
                initialValue = _state.value.toUiState()
            )

    private val _effects = MutableSharedFlow<WorkoutEffect>()
    val effects: SharedFlow<WorkoutEffect> = _effects

    private val sendMutex = Mutex()

    // Connection monitoring configuration
    private var consecutiveFail = 0
    private val failThreshold = 3
    private var heartbeatJob: Job? = null
    private var onlineUntilMs: Long = 0L
    private val heartbeatIntervalMs = 5_000L
    private val stickyOnlineMs = 15_000L

    /**
     * Starts workout session and connection monitoring
     */
    fun start() {
        if (_state.value.isRunning) return
        dispatch(WorkoutAction.Start)
        maybeSpeak("開始します")
        startHeartbeat()
        pingHealth()
    }

    /**
     * Stops workout session and connection monitoring
     */
    fun stop() {
        if (!_state.value.isRunning) return
        dispatch(WorkoutAction.Stop)
        stopHeartbeat()
        maybeSpeak("停止しました")
    }

    /**
     * Resets workout session state both locally and on server
     */
    fun reset() {
        val currentMode = _state.value.exerciseMode
        viewModelScope.launch(io) {
            val response = runCatching { api.resetSession(currentMode) }.getOrNull()
            if (response != null) {
                dispatch(WorkoutAction.SetRep(response.repCount))
                dispatch(WorkoutAction.SetAngle(response.angle))
                dispatch(WorkoutAction.SetPosition(response.position))
                dispatch(WorkoutAction.SetMotivation(response.motivation))
                markOnline()
            } else {
                dispatch(WorkoutAction.Reset)
                bumpFailAndMaybeOffline()
            }
        }
        maybeSpeak("リセットしました")
    }

    /**
     * Processes camera frame for exercise analysis.
     * Thread-safe frame processing with mutex to prevent concurrent API calls.
     */
    fun onFrameJpeg(jpeg: ByteArray, rotationDegrees: Int) {
        if (!_state.value.isRunning) return

        val currentMode = _state.value.exerciseMode
        viewModelScope.launch(io) {
            val locked = sendMutex.tryLock()
            if (!locked) return@launch
            try {
                val response = runCatching {
                    api.sendFrameJpeg(jpeg, rotationDegrees, currentMode)
                }.getOrNull()

                if (response != null) {
                    markOnline()

                    val currentState = _state.value
                    val currentRep = currentState.repCount
                    val currentMotivation = currentState.motivation

                    dispatch(WorkoutAction.SetRep(response.repCount))
                    dispatch(WorkoutAction.SetAngle(response.angle))
                    dispatch(WorkoutAction.SetPosition(response.position))
                    dispatch(WorkoutAction.SetMotivation(response.motivation))

                    // Announce new reps with TTS
                    if(response.motivation != currentMotivation && response.motivation.isNotBlank()){
                        maybeSpeak(response.motivation)
                    }
                } else {
                    bumpFailAndMaybeOffline()
                }
            } finally {
                sendMutex.unlock()
            }
        }
    }

    /**
     * Manual health check trigger
     */
    fun pingHealth() {
        viewModelScope.launch(io) {
            val ok = runCatching { api.health() }.getOrElse { false }
            if (ok) markOnline() else bumpFailAndMaybeOffline()
        }
    }

    // Connection monitoring implementation

    private fun startHeartbeat() {
        if (heartbeatJob?.isActive == true) return
        dispatch(WorkoutAction.SetConnection(ConnectionStatus.Connecting))

        heartbeatJob = viewModelScope.launch(io) {
            while (isActive) {
                val ok = runCatching { api.health() }.getOrElse { false }
                if (ok) markOnline() else bumpFailAndMaybeOffline()
                delay(heartbeatIntervalMs)
            }
        }
    }

    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
        consecutiveFail = 0
    }

    /**
     * Marks connection as healthy and extends online status
     */
    private fun markOnline() {
        val now = System.currentTimeMillis()
        onlineUntilMs = maxOf(onlineUntilMs, now + stickyOnlineMs)
        consecutiveFail = 0
        dispatch(WorkoutAction.SetConnection(ConnectionStatus.Online))
    }

    /**
     * Increments failure count and updates connection status based on thresholds
     */
    private fun bumpFailAndMaybeOffline() {
        consecutiveFail++
        val now = System.currentTimeMillis()
        if (consecutiveFail >= failThreshold && now > onlineUntilMs) {
            dispatch(WorkoutAction.SetConnection(ConnectionStatus.Offline))
        } else {
            dispatch(WorkoutAction.SetConnection(ConnectionStatus.Connecting))
        }
    }

    private fun dispatch(a: WorkoutAction) {
        _state.update { s -> reduce(s, a) }
    }

    /**
     * Sends text to TTS engine and emits speech effect
     */
    private fun maybeSpeak(text: String) {
        tts?.speak(text)
        viewModelScope.launch { _effects.emit(WorkoutEffect.Speak(text)) }
    }
}