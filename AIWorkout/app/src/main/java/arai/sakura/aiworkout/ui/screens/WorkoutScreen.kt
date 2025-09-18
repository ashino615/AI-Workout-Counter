package arai.sakura.aiworkout.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalInspectionMode
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import arai.sakura.aiworkout.ui.components.CameraViewWithPermission
import arai.sakura.aiworkout.ui.components.CommentCard
import arai.sakura.aiworkout.ui.components.ConnectionStatus
import arai.sakura.aiworkout.ui.components.ConnectionStatusChip
import arai.sakura.aiworkout.ui.components.ControlButtonsPanel
import arai.sakura.aiworkout.ui.components.StatusDisplayPanel


/**
 * UI state model for workout screen display.
 * Lightweight data class optimized for Compose rendering.
 */
data class WorkoutUiState(
    val isRunning: Boolean = false,
    val repCount: Int = 0,
    val angle: Float? = null,
    val position: String? = null,
    val motivation: String = "準備OK！",
    val connection: ConnectionStatus = ConnectionStatus.Offline,
    val exerciseMode: String = "chinup"
)

/**
 * Main workout screen featuring side-by-side layout:
 * - Left: Camera preview with stats overlay and connection status
 * - Right: Fixed-width control panel with workout controls and motivation
 *
 * The camera occupies remaining space while controls maintain consistent width.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WorkoutScreen(
    uiState: WorkoutUiState,
    onStart: () -> Unit,
    onStop: () -> Unit,
    onReset: () -> Unit,
    onFrameJpeg: (jpeg: ByteArray, rotationDegrees: Int) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val panelWidth = 280.dp // Fixed width for right control panel

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "カウンター",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "戻る"
                        )
                    }
                }
            )
        }
    ) { padding ->
        Row(
            modifier = modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalArrangement = Arrangement.Start,
            verticalAlignment = Alignment.Top
        ) {

            // Left: Camera preview area (takes remaining space)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .background(Color(0xFFEDEDED), RoundedCornerShape(16.dp))
            ) {
                val inPreview = LocalInspectionMode.current
                if (inPreview) {
                    // Preview placeholder for design-time rendering
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color(0xFFCCCCCC), RoundedCornerShape(16.dp)),
                        contentAlignment = Alignment.Center
                    ) { Text("Camera Preview", color = Color.DarkGray) }
                } else {
                    CameraViewWithPermission(
                        isActive = uiState.isRunning,
                        onFrameJpeg = onFrameJpeg,
                        modifier = Modifier
                            .fillMaxSize()
                            .background(Color.Black, RoundedCornerShape(16.dp)),
                        targetFps = 5
                    )
                }

                // Top-left: Connection status indicator
                ConnectionStatusChip(
                    status = uiState.connection,
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .padding(12.dp)
                )

                CommentCard(
                    comment = uiState.motivation,
                    modifier = Modifier
                        .align(Alignment.BottomCenter)
                        .padding(12.dp)
                        .fillMaxWidth(0.9f)
                )
            }

            Spacer(Modifier.width(12.dp))

            // Right: Fixed-width control panel
            Column(
                modifier = Modifier
                    .width(280.dp)
                    .fillMaxHeight(),
                verticalArrangement = Arrangement.spacedBy(16.dp),
                horizontalAlignment = Alignment.Start
            ) {
                StatusDisplayPanel(
                    repCount = uiState.repCount,
                    angle = uiState.angle,
                    position = uiState.position,
                    modifier = Modifier.fillMaxWidth()
                )
                ControlButtonsPanel(
                    isRunning = uiState.isRunning,
                    onstart = onStart,
                    onStop = onStop,
                    onReset = onReset,
                    modifier = Modifier.fillMaxWidth()
                )

                Spacer(Modifier.weight(1f))
            }
        }
    }
}