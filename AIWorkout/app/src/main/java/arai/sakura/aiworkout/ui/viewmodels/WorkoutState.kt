package arai.sakura.aiworkout.ui.viewmodels

import arai.sakura.aiworkout.ui.components.ConnectionStatus
import arai.sakura.aiworkout.ui.screens.WorkoutUiState

/**
 * Domain state model for workout session data.
 *
 * Maintains exercise state independently of Android/Compose dependencies
 * for improved testability. UI layer receives this data transformed via toUiState().
 */
data class WorkoutState(
    val isRunning: Boolean = false,
    val repCount: Int = 0,
    val angle: Float? = null,
    val position: String? = null,
    val motivation: String = "準備OK！",
    val connection: ConnectionStatus = ConnectionStatus.Offline,
    val exerciseMode: String = "chinup"
)

/**
 * One-time side effects that don't belong in state
 */
sealed interface WorkoutEffect {
    data class Speak(val text: String) : WorkoutEffect
    data class Toast(val message: String) : WorkoutEffect
}

/**
 * State update actions processed by the ViewModel reducer.
 * Each action represents a specific state change operation.
 */
sealed interface WorkoutAction {
    data object Start : WorkoutAction
    data object Stop : WorkoutAction
    data object Reset : WorkoutAction
    data class SetConnection(val status: ConnectionStatus) : WorkoutAction
    data class SetRep(val value: Int) : WorkoutAction
    data class SetAngle(val value: Float?) : WorkoutAction
    data class SetPosition(val value: String?) : WorkoutAction
    data class SetMotivation(val value: String) : WorkoutAction
    data class SetExerciseMode(val mode: String) : WorkoutAction
}

/**
 * Pure function that creates new state from current state + action.
 * All state transitions are handled here for predictable behavior.
 */
fun reduce(state: WorkoutState, action: WorkoutAction): WorkoutState =
    when (action) {
        WorkoutAction.Start -> state.copy(isRunning = true)
        WorkoutAction.Stop  -> state.copy(isRunning = false)
        WorkoutAction.Reset -> state.copy(repCount = 0, angle = null, position = null, motivation = "リセットしました")
        is WorkoutAction.SetConnection -> state.copy(connection = action.status)
        is WorkoutAction.SetRep        -> state.copy(repCount = action.value)
        is WorkoutAction.SetAngle      -> state.copy(angle = action.value)
        is WorkoutAction.SetPosition   -> state.copy(position = action.value)
        is WorkoutAction.SetMotivation -> state.copy(motivation = action.value)
        is WorkoutAction.SetExerciseMode -> state.copy(exerciseMode = action.mode)
    }

/**
 * Converts domain state to UI-specific state model
 */
fun WorkoutState.toUiState(): WorkoutUiState = WorkoutUiState(
    isRunning = isRunning,
    repCount = repCount,
    angle = angle,
    position = position,
    motivation = motivation,
    connection = connection,
    exerciseMode = exerciseMode
)