package arai.sakura.aiworkout.utils

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.ConnectionPool
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * API response model for workout analysis results
 */
@Serializable
data class WorkoutResponse(
    val repCount: Int = 0,
    val angle: Float? = null,
    val position: String? = null,
    val motivation: String = "Let's get started!",
    val isWorkoutActive: Boolean = false,
    val isConnected: Boolean = false,
    val errorMessage: String? = null,
    val framesSent: Int = 0,
    val lastRepAt: Long = 0
)

/**
 * HTTP client for workout analysis API communication.
 * Handles frame upload, session management, and health checks.
 */
class ApiService private constructor(
    private val baseUrl: String,
    private val client: OkHttpClient
) {
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    /**
     * Health check endpoint to verify API availability
     * @return true if API is responding, false otherwise
     */
    suspend fun health(): Boolean = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("${baseUrl}health").get().build()
        runCatching { client.newCall(req).execute().use { it.isSuccessful } }.getOrElse { false }
    }

    /**
     * Uploads JPEG frame for workout analysis
     * @param bytes JPEG image data
     * @param rotation Image rotation in degrees
     * @param mode Exercise type (chinup, pushup, squat, armcurl)
     * @return Analysis results or null if request failed
     */
    suspend fun sendFrameJpeg(bytes: ByteArray, rotation: Int, mode: String = "chinup"): WorkoutResponse? =
        withContext(Dispatchers.IO) {
            val body = MultipartBody.Builder().setType(MultipartBody.FORM)
                .addFormDataPart(
                    "file", "frame.jpg",
                    bytes.toRequestBody("image/jpeg".toMediaType(), 0, bytes.size)
                )
                .addFormDataPart("mode", mode)
                .build()

            val req = Request.Builder()
                .url("${baseUrl}analyze_frame")
                .post(body)
                .build()

            runCatching {
                client.newCall(req).execute().use { response ->
                    if (response.isSuccessful) {
                        val responseBody = response.body?.string()
                        if (responseBody != null) {
                            println("API Response: $responseBody") // Debug log
                            val workoutResponse = json.decodeFromString<WorkoutResponse>(responseBody)
                            println("Parsed - Reps: ${workoutResponse.repCount}, Angle: ${workoutResponse.angle}, Position: ${workoutResponse.position}") // Debug log
                            workoutResponse
                        } else {
                            println("API Response body was null")
                            null
                        }
                    } else {
                        println("API Response not successful: ${response.code} - ${response.message}")
                        null
                    }
                }
            }.getOrElse { exception ->
                println("API Exception: ${exception.message}")
                null
            }
        }

    /**
     * Resets workout session state on server
     * @param mode Exercise type to reset
     * @return Reset confirmation or null if failed
     */
    suspend fun resetSession(mode: String = "chinup"): WorkoutResponse? = withContext(Dispatchers.IO) {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("mode", mode).build()
        val req = Request.Builder().url("${baseUrl}reset_session").post(body).build()

        runCatching {
            client.newCall(req).execute().use { response ->
                if (response.isSuccessful) {
                    val responseBody = response.body?.string()
                    if (responseBody != null) {
                        json.decodeFromString<WorkoutResponse>(responseBody)
                    } else null
                } else null
            }
        }.getOrNull()
    }


    companion object {
        /**
         * Creates ApiService instance with configured HTTP client
         * @param baseUrl API server base URL (trailing slash will be added if missing)
         */
        fun create(baseUrl: String): ApiService {
            val client = OkHttpClient.Builder()
                .connectionPool(ConnectionPool(5, 60, TimeUnit.SECONDS))
                .connectTimeout(5, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS)
                .writeTimeout(10, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build()
            val normalized = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
            return ApiService(normalized, client)
        }
    }
}