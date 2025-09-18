package arai.sakura.aiworkout.ui.components

import android.Manifest
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.SystemClock
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.accompanist.permissions.ExperimentalPermissionsApi
import com.google.accompanist.permissions.rememberPermissionState
import com.google.accompanist.permissions.isGranted
import com.google.accompanist.permissions.shouldShowRationale
import java.io.ByteArrayOutputStream
import kotlin.math.max

/**
 * Camera integration components for workout frame capture and analysis.
 *
 * Provides:
 * - Permission-aware camera view with automatic request handling
 * - FPS-throttled frame processing with JPEG conversion
 * - Lifecycle-aware camera binding and cleanup
 */

/* ─────────────────────────────────────────────────────── */
/* Main camera component with permission handling           */
/* ─────────────────────────────────────────────────────── */

/**
 * Complete camera view with automatic permission management.
 * Handles permission states and displays appropriate UI for each state.
 */
@OptIn(ExperimentalPermissionsApi::class)
@Composable
fun CameraViewWithPermission(
    isActive: Boolean,
    onFrameJpeg: (jpeg: ByteArray, rotationDegrees: Int) -> Unit,
    modifier: Modifier = Modifier,
    targetFps: Int = 5,
    lensFacing: Int = CameraSelector.LENS_FACING_BACK
) {
    val camPerm = rememberPermissionState(Manifest.permission.CAMERA)

    when {
        camPerm.status.isGranted -> {
            CameraView(
                isActive = isActive,
                onFrameJpeg = onFrameJpeg,
                modifier = modifier,
                targetFps = targetFps,
                lensFacing = lensFacing
            )
        }
        camPerm.status.shouldShowRationale -> {
            PermissionRationale(
                text = "カメラ権限が必要です。計測のためにカメラへのアクセスを許可してください。",
                onRequest = { camPerm.launchPermissionRequest() },
                modifier = modifier
            )
        }
        else -> {
            PermissionRequest(
                text = "カメラ権限が未許可です。許可してカメラを開始します。",
                onRequest = { camPerm.launchPermissionRequest() },
                modifier = modifier
            )
        }
    }
}

/* ─────────────────────────────────────────────────────── */
/* Core camera implementation with preview and analysis     */
/* ─────────────────────────────────────────────────────── */

/**
 * Camera view implementation with preview and optional frame analysis.
 * When active, captures frames at specified FPS and converts to JPEG for processing.
 */
@Composable
fun CameraView(
    isActive: Boolean,
    onFrameJpeg: (jpeg: ByteArray, rotationDegrees: Int) -> Unit,
    modifier: Modifier = Modifier,
    targetFps: Int = 5,
    lensFacing: Int = CameraSelector.LENS_FACING_BACK
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val previewView = remember {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
    }

    val cameraProviderFuture = remember { ProcessCameraProvider.getInstance(context) }
    val currentOnFrame by rememberUpdatedState(onFrameJpeg)

    AndroidView(
        modifier = modifier,
        factory = { previewView }
    )

    // Camera lifecycle management with automatic cleanup
    DisposableEffect(isActive, targetFps, lensFacing) {
        val executor = ContextCompat.getMainExecutor(context)
        val listener = Runnable {
            val cameraProvider = cameraProviderFuture.get()
            cameraProvider.unbindAll()

            // Configure camera preview
            val preview = Preview.Builder()
                .build()
                .also { it.setSurfaceProvider(previewView.surfaceProvider) }

            // Configure frame analysis (only when workout is active)
            val analysis = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
                .apply {
                    if (isActive) {
                        setAnalyzer(
                            executor,
                            ThrottledJpegAnalyzer(
                                fps = targetFps,
                                emit = { bytes, rotation ->
                                    currentOnFrame(bytes, rotation)
                                }
                            )
                        )
                    }
                }

            val selector = CameraSelector.Builder()
                .requireLensFacing(lensFacing)
                .build()

            // Bind appropriate use cases based on active state
            if (isActive) {
                cameraProvider.bindToLifecycle(lifecycleOwner, selector, preview, analysis)
            } else {
                cameraProvider.bindToLifecycle(lifecycleOwner, selector, preview)
            }
        }

        cameraProviderFuture.addListener(listener, executor)

        onDispose {
            try {
                cameraProviderFuture.get().unbindAll()
            } catch (_: Throwable) { /* Safe cleanup on disposal */ }
        }
    }
}

/* ─────────────────────────────────────────────────────── */
/* Permission UI components                                  */
/* ─────────────────────────────────────────────────────── */

/**
 * UI shown when camera permission needs to be requested initially
 */
@Composable
private fun PermissionRequest(
    text: String,
    onRequest: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(text)
            Button(onClick = onRequest) { Text("許可する") }
        }
    }
}

/**
 * UI shown when permission was denied but can be requested again
 */
@Composable
private fun PermissionRationale(
    text: String,
    onRequest: () -> Unit,
    modifier: Modifier = Modifier
) {
    Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(text)
            OutlinedButton(onClick = onRequest) { Text("再リクエスト") }
        }
    }
}

/* ─────────────────────────────────────────────────────── */
/* Frame processing implementation                           */
/* ─────────────────────────────────────────────────────── */

/**
 * ImageAnalysis.Analyzer that throttles frame processing to target FPS
 * and performs YUV to JPEG conversion for network transmission.
 */
private class ThrottledJpegAnalyzer(
    fps: Int,
    private val emit: (jpeg: ByteArray, rotationDegrees: Int) -> Unit
) : ImageAnalysis.Analyzer {

    private val minIntervalMs = 1000L / max(1, fps)
    private var lastEmitAt = 0L

    override fun analyze(image: ImageProxy) {
        val now = SystemClock.elapsedRealtime()
        try {
            if (now - lastEmitAt >= minIntervalMs) {
                // Convert YUV frame to NV21, then compress to JPEG
                val nv21 = image.toNV21()
                val yuv = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
                val out = ByteArrayOutputStream()
                yuv.compressToJpeg(Rect(0, 0, image.width, image.height), /*quality=*/80, out)
                emit(out.toByteArray(), image.imageInfo.rotationDegrees)
                lastEmitAt = now
            }
        } finally {
            image.close()
        }
    }
}

/**
 * Converts ImageProxy (YUV_420_888) to NV21 byte array.
 * Handles both optimized and fallback conversion paths for device compatibility.
 */
private fun ImageProxy.toNV21(): ByteArray {
    val yPlane = planes[0].buffer
    val uPlane = planes[1].buffer
    val vPlane = planes[2].buffer

    val ySize = yPlane.remaining()
    val uSize = uPlane.remaining()
    val vSize = vPlane.remaining()

    // NV21: Y data followed by interleaved VU data
    val nv21 = ByteArray(ySize + uSize + vSize)

    yPlane.get(nv21, 0, ySize)

    val chromaRowStride = planes[1].rowStride
    val chromaPixelStride = planes[1].pixelStride

    // Optimized path for typical case (pixel stride = 2, row stride = width)
    if (chromaPixelStride == 2 && chromaRowStride == width) {
        // Direct VU interleaving
        var offset = ySize
        val uvBuffer = ByteArray(uSize + vSize)
        vPlane.get(uvBuffer, 0, vSize)
        uPlane.get(uvBuffer, vSize, uSize)

        var i = 0
        while (i < uvBuffer.size) {
            // NV21 format: V then U
            nv21[offset++] = uvBuffer[i]
            nv21[offset++] = uvBuffer[i + 1]
            i += 2
        }
    } else {
        // Fallback: pixel-by-pixel scanning for non-standard formats
        var offset = ySize
        val width = width
        val height = height
        val chromaHeight = height / 2
        val chromaWidth = width / 2

        val uBuffer = planes[1].buffer
        val vBuffer = planes[2].buffer
        val uRowStride = planes[1].rowStride
        val vRowStride = planes[2].rowStride
        val uPixelStride = planes[1].pixelStride
        val vPixelStride = planes[2].pixelStride

        for (row in 0 until chromaHeight) {
            for (col in 0 until chromaWidth) {
                val vu = (row * vRowStride + col * vPixelStride)
                val uu = (row * uRowStride + col * uPixelStride)
                nv21[offset++] = vBuffer.get(vu)
                nv21[offset++] = uBuffer.get(uu)
            }
        }
    }
    return nv21
}
