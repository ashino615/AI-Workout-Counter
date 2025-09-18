package arai.sakura.aiworkout.utils

import android.content.Context
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
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import java.io.ByteArrayOutputStream
import kotlin.math.max

/**
 * CameraX utility helper providing common camera operations:
 * - Image format conversion (YUV_420_888 to NV21 to JPEG)
 * - FPS-throttled frame analysis
 * - Simple camera setup with preview and analysis
 *
 * Note: This provides similar functionality to CameraComponents.kt but as a reusable utility.
 * Consider consolidating implementations if both are used in the same codebase.
 */
object CameraHelper {

    /* ─────────────────────────────────────────────────────── */
    /* Image format conversion utilities                        */
    /* ─────────────────────────────────────────────────────── */

    /**
     * Converts ImageProxy (YUV_420_888 format) to NV21 byte array.
     * NV21 format: Y plane followed by interleaved VU data.
     */
    fun ImageProxy.toNV21(): ByteArray {
        val yPlane = planes[0].buffer
        val uPlane = planes[1].buffer
        val vPlane = planes[2].buffer

        val ySize = yPlane.remaining()
        val uSize = uPlane.remaining()
        val vSize = vPlane.remaining()

        val nv21 = ByteArray(ySize + uSize + vSize)
        yPlane.get(nv21, 0, ySize)

        val chromaRowStride = planes[1].rowStride
        val chromaPixelStride = planes[1].pixelStride

        // Optimized path for typical case (pixel stride = 2, row stride = width)
        if (chromaPixelStride == 2 && chromaRowStride == width) {
            var offset = ySize
            val uv = ByteArray(uSize + vSize)
            vPlane.get(uv, 0, vSize)
            uPlane.get(uv, vSize, uSize)
            var i = 0
            while (i < uv.size) {
                nv21[offset++] = uv[i]     // V
                nv21[offset++] = uv[i + 1] // U
                i += 2
            }
        } else {
            // Fallback: pixel-by-pixel scanning for non-standard formats
            var offset = ySize
            val width = width
            val height = height
            val cw = width / 2
            val ch = height / 2

            val uBuf = planes[1].buffer
            val vBuf = planes[2].buffer
            val uRow = planes[1].rowStride
            val vRow = planes[2].rowStride
            val uPix = planes[1].pixelStride
            val vPix = planes[2].pixelStride

            for (row in 0 until ch) {
                for (col in 0 until cw) {
                    val vu = row * vRow + col * vPix
                    val uu = row * uRow + col * uPix
                    nv21[offset++] = vBuf.get(vu)
                    nv21[offset++] = uBuf.get(uu)
                }
            }
        }
        return nv21
    }

    /**
     * Compresses NV21 data to JPEG format
     * @param quality JPEG quality (0-100, higher = better quality)
     */
    fun nv21ToJpeg(nv21: ByteArray, width: Int, height: Int, quality: Int = 80): ByteArray {
        val yuv = YuvImage(nv21, ImageFormat.NV21, width, height, null)
        val out = ByteArrayOutputStream()
        yuv.compressToJpeg(Rect(0, 0, width, height), quality, out)
        return out.toByteArray()
    }

    /**
     * Direct conversion from ImageProxy to JPEG
     * @return Pair of (JPEG bytes, rotation degrees)
     */
    fun ImageProxy.toJpeg(quality: Int = 80): Pair<ByteArray, Int> {
        val nv21 = toNV21()
        val jpeg = nv21ToJpeg(nv21, width, height, quality)
        return jpeg to imageInfo.rotationDegrees
    }

    /* ─────────────────────────────────────────────────────── */
    /* FPS-throttled frame analyzer                             */
    /* ─────────────────────────────────────────────────────── */

    /**
     * ImageAnalysis.Analyzer that throttles frame processing to target FPS
     * and converts frames to JPEG before emitting.
     */
    class FpsThrottledAnalyzer(
        fps: Int,
        private val quality: Int = 80,
        private val emit: (jpeg: ByteArray, rotationDegrees: Int) -> Unit
    ) : ImageAnalysis.Analyzer {
        private val minIntervalMs = 1000L / max(1, fps)
        private var lastEmitAt = 0L

        override fun analyze(image: ImageProxy) {
            val now = SystemClock.elapsedRealtime()
            try {
                if (now - lastEmitAt >= minIntervalMs) {
                    val (jpeg, rotation) = image.toJpeg(quality)
                    emit(jpeg, rotation)
                    lastEmitAt = now
                }
            } finally {
                image.close()
            }
        }
    }

    /**
     * Creates pre-configured ImageAnalysis instance with FPS throttling
     * Note: Requires context for executor setup
     */
    fun buildAnalyzer(
        context: Context,
        fps: Int = 5,
        quality: Int = 80,
        emit: (jpeg: ByteArray, rotationDegrees: Int) -> Unit
    ): ImageAnalysis =
        ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .apply {
                setAnalyzer(
                    ContextCompat.getMainExecutor(context),
                    FpsThrottledAnalyzer(fps, quality, emit)
                )
            }

    /* ─────────────────────────────────────────────────────── */
    /* Complete camera setup utility                            */
    /* ─────────────────────────────────────────────────────── */

    /**
     * Convenience method to set up camera with preview and analysis in one call.
     * Handles camera provider binding and provides cleanup via AutoCloseable.
     *
     * @param isActive Whether to enable frame analysis (false = preview only)
     * @return AutoCloseable that unbinds camera when closed
     */
    fun bindToLifecycle(
        context: Context,
        lifecycleOwner: LifecycleOwner,
        previewView: PreviewView,
        isActive: Boolean,
        targetFps: Int = 5,
        lensFacing: Int = CameraSelector.LENS_FACING_BACK,
        emit: (jpeg: ByteArray, rotationDegrees: Int) -> Unit
    ): AutoCloseable {
        val cameraProvider = ProcessCameraProvider.getInstance(context).get()
        cameraProvider.unbindAll()

        // Configure preview
        val preview = Preview.Builder()
            .build()
            .also { it.setSurfaceProvider(previewView.surfaceProvider) }

        // Configure analysis (only bind if active)
        val analysis = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .build()
            .apply {
                if (isActive) {
                    setAnalyzer(
                        ContextCompat.getMainExecutor(context),
                        FpsThrottledAnalyzer(fps = targetFps, emit = emit)
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

        return AutoCloseable { runCatching { cameraProvider.unbindAll() } }
    }
}