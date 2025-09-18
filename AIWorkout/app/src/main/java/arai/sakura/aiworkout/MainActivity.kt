package arai.sakura.aiworkout

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.annotation.RawRes
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import arai.sakura.aiworkout.ui.components.ConnectionStatus
import arai.sakura.aiworkout.ui.screens.WorkoutScreen
import arai.sakura.aiworkout.ui.theme.AIWorkoutTheme
import arai.sakura.aiworkout.ui.viewmodels.WorkoutViewModel
import arai.sakura.aiworkout.utils.ApiService
import arai.sakura.aiworkout.utils.TTSHelper
import coil.compose.AsyncImage
import coil.decode.SvgDecoder
import coil.imageLoader
import coil.request.CachePolicy
import coil.request.ImageRequest

// Screen navigation states
private enum class AppScreen { Home, Workout, HowToPushUp, HowToPullUp, HowToSquat, HowToArmCurl }

// Theme modes for the application
enum class ThemeMode { Light, Dark, System }

class MainActivity : ComponentActivity() {

    private lateinit var tts: TTSHelper
    private lateinit var viewModel: WorkoutViewModel

    companion object {
        // Server endpoint configuration
        private const val BASE_URL = "http://192.168.137.1:8000/"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Configure fullscreen display
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior =
                WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }

        tts = TTSHelper(this)
        val api = ApiService.create(BASE_URL)

        viewModel = ViewModelProvider(this, WorkoutVmFactory(api, tts))
            .get(WorkoutViewModel::class.java)

        setContent {
            val systemDark = androidx.compose.foundation.isSystemInDarkTheme()

            // User's theme preference (survives process recreation)
            var themeMode by rememberSaveable { mutableStateOf(ThemeMode.System) }

            // Calculate current dark flag
            val isDark = when (themeMode) {
                ThemeMode.System -> systemDark
                ThemeMode.Light  -> false
                ThemeMode.Dark   -> true
            }

            AIWorkoutTheme(darkTheme = isDark, dynamicColor = true) {
                var screen by remember { mutableStateOf(AppScreen.Home) }
                val ui by viewModel.uiState.collectAsState()

                when (screen) {
                    AppScreen.Home -> HomeScreen(
                        connection = ui.connection,

                        // Exercise counter navigation - using specific methods from functional version
                        onStartPushUp = {
                            // Use the specific method if it exists, otherwise fall back to generic start
                            if (::viewModel.isInitialized) {
                                try {
                                    viewModel::class.java.getMethod("startPushUp").invoke(viewModel)
                                } catch (e: NoSuchMethodException) {
                                    viewModel.start()
                                }
                            }
                            screen = AppScreen.Workout
                        },
                        onStartPullUp = {
                            try {
                                viewModel::class.java.getMethod("startPullUp").invoke(viewModel)
                            } catch (e: NoSuchMethodException) {
                                viewModel.start()
                            }
                            screen = AppScreen.Workout
                        },
                        onStartSquat = {
                            try {
                                viewModel::class.java.getMethod("startSquat").invoke(viewModel)
                            } catch (e: NoSuchMethodException) {
                                viewModel.start()
                            }
                            screen = AppScreen.Workout
                        },
                        onStartArmCurl = {
                            try {
                                viewModel::class.java.getMethod("startArmCurl").invoke(viewModel)
                            } catch (e: NoSuchMethodException) {
                                viewModel.start()
                            }
                            screen = AppScreen.Workout
                        },

                        // How-to tutorial navigation
                        onHowToPushUp = { screen = AppScreen.HowToPushUp },
                        onHowToPullUp = { screen = AppScreen.HowToPullUp },
                        onHowToSquat = { screen = AppScreen.HowToSquat },
                        onHowToArmCurl = { screen = AppScreen.HowToArmCurl },
                        topBarActions = {
                            ThemeSwitcher(
                                mode = themeMode,
                                onModeChange = { themeMode = it }
                            )
                        }
                    )

                    AppScreen.Workout -> {
                        WorkoutScreen(
                            uiState = ui,
                            onStart = viewModel::start,
                            onStop = viewModel::stop,
                            onReset = viewModel::reset,
                            onFrameJpeg = viewModel::onFrameJpeg,
                            onBack = { screen = AppScreen.Home }
                        )
                    }

                    AppScreen.HowToPushUp -> {
                        HowToPushUpScreen(
                            videoRes = R.raw.pushup_video,
                            onBack = { screen = AppScreen.Home },
                            topBarActions = {
                                ThemeSwitcher(
                                    mode = themeMode,
                                    onModeChange = { themeMode = it }
                                )
                            }
                        )
                    }

                    AppScreen.HowToPullUp -> {
                        HowToPullUpScreen(
                            videoRes = R.raw.pullup_video,
                            onBack = { screen = AppScreen.Home },
                            topBarActions = {
                                ThemeSwitcher(
                                    mode = themeMode,
                                    onModeChange = { themeMode = it }
                                )
                            }
                        )
                    }
                    AppScreen.HowToSquat -> {
                        HowToSquatScreen(
                            videoRes = R.raw.squat_video,
                            onBack = { screen = AppScreen.Home },
                            topBarActions = {
                                ThemeSwitcher(
                                    mode = themeMode,
                                    onModeChange = { themeMode = it }
                                )
                            }
                        )
                    }
                    AppScreen.HowToArmCurl -> {
                        HowToArmCurlScreen(
                            videoRes = R.raw.armcurl_video,
                            onBack = { screen = AppScreen.Home },
                            topBarActions = {
                                ThemeSwitcher(
                                    mode = themeMode,
                                    onModeChange = { themeMode = it }
                                )
                            }
                        )
                    }
                }
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        tts.shutdown()
    }
}

/**
 * Factory for creating WorkoutViewModel with required dependencies
 */
private class WorkoutVmFactory(
    private val api: ApiService,
    private val tts: TTSHelper?
) : ViewModelProvider.Factory {
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(WorkoutViewModel::class.java)) {
            @Suppress("UNCHECKED_CAST")
            return WorkoutViewModel(api = api, tts = tts) as T
        }
        throw IllegalArgumentException("Unknown ViewModel: ${modelClass.name}")
    }
}

/**
 * Home screen displaying exercise options in a 2-column grid layout with theming support.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HomeScreen(
    connection: ConnectionStatus,
    onStartPushUp: () -> Unit,
    onStartPullUp: () -> Unit,
    onStartSquat: () -> Unit,
    onStartArmCurl: () -> Unit,
    onHowToPushUp: () -> Unit,
    onHowToPullUp: () -> Unit,
    onHowToSquat: () -> Unit,
    onHowToArmCurl: () -> Unit,
    topBarActions: @Composable RowScope.() -> Unit
) {
    val connectedLabel = when (connection) {
        ConnectionStatus.Online -> "connected"
        ConnectionStatus.Connecting -> "connecting..."
        ConnectionStatus.Offline -> "offline"
    }

    // Exercise tile configuration with colors and SVG resources
    data class Tile(
        val title: String,
        val onClick: () -> Unit,
        @RawRes val svgRes: Int? = null
    )

    val tiles = listOf(
        // Counter tiles (blue theme) / How-to tiles (green theme)
        Tile("Push up Counter", onClick = onStartPushUp,  svgRes = R.raw.pushup),
        Tile("How to Push up", onClick = onHowToPushUp,   svgRes = R.raw.pushup),

        Tile("Pull up Counter", onClick = onStartPullUp,  svgRes = R.raw.pullup),
        Tile("How to Pull up", onClick = onHowToPullUp,  svgRes = R.raw.pullup),

        Tile("Squat Counter", onClick = onStartSquat,   svgRes = R.raw.squat),
        Tile("How to Squat",  onClick = onHowToSquat,   svgRes = R.raw.squat),

        Tile("Arm Curl Counter", onClick = onStartArmCurl, svgRes = R.raw.arm),
        Tile("How to Arm Curl", onClick = onHowToArmCurl, svgRes = R.raw.arm)
    )

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "HOME",
                            modifier = Modifier.alignByBaseline(),
                            style = MaterialTheme.typography.titleLarge
                        )
                        Spacer(Modifier.width(16.dp))
                        Text(
                            text = "接続状態：$connectedLabel",
                            modifier = Modifier.alignByBaseline(),
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = { topBarActions() }
            )
        }
    ) { padding ->
        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            modifier = Modifier
                .padding(padding)
                .padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(28.dp),
            horizontalArrangement = Arrangement.spacedBy(28.dp),
            contentPadding = PaddingValues(bottom = 32.dp)
        ) {
            items(tiles) { t ->
                val isHowTo = t.title.startsWith("How to")
                TileCard(
                    title = t.title,
                    tint = if (isHowTo) {
                        MaterialTheme.colorScheme.secondaryContainer
                    }else{
                        MaterialTheme.colorScheme.primaryContainer
                    },
                    imageTint = if(isHowTo){
                        MaterialTheme.colorScheme.onSecondaryContainer
                    }else{
                        MaterialTheme.colorScheme.onPrimaryContainer
                    },
                    onClick = t.onClick,
                    tileHeight = 200.dp,
                    svgRes = t.svgRes
                )
            }
        }
    }
}

/**
 * Individual exercise tile card with SVG icon and centered text.
 */
@Composable
private fun TileCard(
    title: String,
    tint: Color = MaterialTheme.colorScheme.primaryContainer,
    imageTint: Color = MaterialTheme.colorScheme.onPrimaryContainer,
    onClick: () -> Unit,
    tileHeight: Dp = 200.dp,
    @RawRes svgRes: Int? = null
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .height(tileHeight),
        elevation = CardDefaults.cardElevation(
            defaultElevation = 8.dp,
            pressedElevation = 12.dp
        )
    ) {
        Surface(
            color = tint,
            shape = MaterialTheme.shapes.large,
            tonalElevation = 2.dp,
            modifier = Modifier
                .fillMaxWidth()
                .height(tileHeight)
                .clickable { onClick() }
        ) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(20.dp),
                horizontalArrangement = Arrangement.spacedBy(20.dp)
            ) { // Left: SVG icon container
                Surface(
                    color = imageTint,
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier
                        .fillMaxHeight()
                        .aspectRatio(1f)
                ) {
                    val context = LocalContext.current
                    val imageLoader = remember(context) {
                        context.imageLoader.newBuilder()
                            .components { add(SvgDecoder.Factory()) }
                            .respectCacheHeaders(false)
                            .build()
                    }
                    if (svgRes != null) {
                        AsyncImage(
                            model = ImageRequest.Builder(context)
                                .data(svgRes)
                                .diskCachePolicy(CachePolicy.ENABLED)
                                .build(),
                            imageLoader = imageLoader,
                            contentDescription = title,
                            modifier = Modifier.fillMaxSize()
                        )
                    } else {
                        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Text(
                                "image",
                                color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.6f)
                            )
                        }
                    }
                }
                // Right: Exercise title text
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .padding(horizontal = 8.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = 2
                    )
                }
            }
        }
    }
}

/**
 * How-to screen for push-up tutorial with theming support.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HowToPushUpScreen(
    @RawRes videoRes: Int,
    onBack: () -> Unit,
    topBarActions: @Composable RowScope.() -> Unit
) {
    val context = LocalContext.current

    // ExoPlayer setup
    val exoPlayer = remember(context) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(
                MediaItem.fromUri("android.resource://${context.packageName}/$videoRes")
            )
            prepare()
            playWhenReady = true
            repeatMode = Player.REPEAT_MODE_ALL
        }
    }
    DisposableEffect(Unit) { onDispose { exoPlayer.release() } }

    // Rotating instructional tips
    val tips = listOf(
        "手は肩幅より少し広めに置く",
        "体幹は一直線をキープ（腰を落とさない）",
        "肘を曲げて胸を床に近づける",
        "胸と肘を意識して押し上げる",
        "呼吸は下げる時に吸い、上げる時に吐く"
    )
    var index by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(5_000)
            index = (index + 1) % tips.size
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("How to Push up", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "戻る"
                        )
                    }
                },
                actions = { topBarActions() }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Video player
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        player = exoPlayer
                        useController = true
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center)
                    .aspectRatio(16f / 9f)
            )

            // Instructional text overlay
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer,
                shape = RoundedCornerShape(8.dp),
                tonalElevation = 2.dp,
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(24.dp)
            ) {
                Text(
                    text = "${index + 1}. ${tips[index]}",
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                )
            }
        }
    }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HowToPullUpScreen(
    @RawRes videoRes: Int,
    onBack: () -> Unit,
    topBarActions: @Composable RowScope.() -> Unit
) {
    val context = LocalContext.current

    // ExoPlayer setup
    val exoPlayer = remember(context) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(
                MediaItem.fromUri("android.resource://${context.packageName}/$videoRes")
            )
            prepare()
            playWhenReady = true
            repeatMode = Player.REPEAT_MODE_ALL
        }
    }
    DisposableEffect(Unit) { onDispose { exoPlayer.release() } }

    // Rotating instructional tips
    val tips = listOf(
        "バーを順手（手の甲が前）でグリップする",
        "手幅は肩幅より少し広めに設定",
        "肩甲骨を下げて胸を張る姿勢を保つ",
        "肘を後ろに引きながら体を引き上げる",
        "顎がバーを越えるまで引き上げる",
    )
    var index by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(5_000)
            index = (index + 1) % tips.size
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("How to Pull up", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "戻る"
                        )
                    }
                },
                actions = { topBarActions() }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Video player
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        player = exoPlayer
                        useController = true
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center)
                    .aspectRatio(16f / 9f)
            )

            // Instructional text overlay
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer,
                shape = RoundedCornerShape(8.dp),
                tonalElevation = 2.dp,
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(24.dp)
            ) {
                Text(
                    text = "${index + 1}. ${tips[index]}",
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                )
            }
        }
    }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HowToSquatScreen(
    @RawRes videoRes: Int,
    onBack: () -> Unit,
    topBarActions: @Composable RowScope.() -> Unit
) {
    val context = LocalContext.current

    // ExoPlayer setup
    val exoPlayer = remember(context) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(
                MediaItem.fromUri("android.resource://${context.packageName}/$videoRes")
            )
            prepare()
            playWhenReady = true
            repeatMode = Player.REPEAT_MODE_ALL
        }
    }
    DisposableEffect(Unit) { onDispose { exoPlayer.release() } }

    // Rotating instructional tips
    val tips = listOf(
        "足は肩幅に開き、つま先は少し外向きに",
        "膝がつま先より前に出ないよう注意",
        "お尻を後ろに引きながらゆっくりおろす",
        "太ももが床と平行になるまで下げる",
        "呼吸は降ろすときに吸い、立ち上がるときに吐く",
    )
    var index by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(5_000)
            index = (index + 1) % tips.size
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("How to Squat", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "戻る"
                        )
                    }
                },
                actions = { topBarActions() }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Video player
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        player = exoPlayer
                        useController = true
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center)
                    .aspectRatio(16f / 9f)
            )

            // Instructional text overlay
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer,
                shape = RoundedCornerShape(8.dp),
                tonalElevation = 2.dp,
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(24.dp)
            ) {
                Text(
                    text = "${index + 1}. ${tips[index]}",
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                )
            }
        }
    }
}
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun HowToArmCurlScreen(
    @RawRes videoRes: Int,
    onBack: () -> Unit,
    topBarActions: @Composable RowScope.() -> Unit
) {
    val context = LocalContext.current

    // ExoPlayer setup
    val exoPlayer = remember(context) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(
                MediaItem.fromUri("android.resource://${context.packageName}/$videoRes")
            )
            prepare()
            playWhenReady = true
            repeatMode = Player.REPEAT_MODE_ALL
        }
    }
    DisposableEffect(Unit) { onDispose { exoPlayer.release() } }

    // Rotating instructional tips
    val tips = listOf(
        "肘を体の横につけて固定する",
        "手のひらを前向きにしてダンベルを握る",
        "ゆっくりとダンベルを肩まで持ち上げる",
        "完全におろし切らず、少し負荷を残す",
        "呼吸は上げるときに吐き、おろすときに吸う",
    )
    var index by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            kotlinx.coroutines.delay(5_000)
            index = (index + 1) % tips.size
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("How to Arm Curl", style = MaterialTheme.typography.titleLarge) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "戻る"
                        )
                    }
                },
                actions = { topBarActions() }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp)
        ) {
            // Video player
            AndroidView(
                factory = { ctx ->
                    PlayerView(ctx).apply {
                        player = exoPlayer
                        useController = true
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center)
                    .aspectRatio(16f / 9f)
            )

            // Instructional text overlay
            Surface(
                color = MaterialTheme.colorScheme.primaryContainer,
                shape = RoundedCornerShape(8.dp),
                tonalElevation = 2.dp,
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(24.dp)
            ) {
                Text(
                    text = "${index + 1}. ${tips[index]}",
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                )
            }
        }
    }
}

/**
 * Enhanced theme switcher with better icons and visual feedback.
 */
@Composable
private fun ThemeSwitcher(
    mode: ThemeMode,
    onModeChange: (ThemeMode) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }

    IconButton(onClick = { expanded = true }) {
        // Better icons that represent the actual theme modes
        val icon = when (mode) {
            ThemeMode.System -> Icons.Filled.Contrast
            ThemeMode.Light  -> Icons.Filled.LightMode
            ThemeMode.Dark   -> Icons.Filled.DarkMode
        }
        Icon(
            imageVector = icon,
            contentDescription = "Theme: ${mode.name}",
            tint = MaterialTheme.colorScheme.onSurface
        )
    }

    DropdownMenu(
        expanded = expanded,
        onDismissRequest = { expanded = false }
    ) {
        ThemeMode.values().forEach { themeMode ->
            DropdownMenuItem(
                text = {
                    Text(
                        text = when (themeMode) {
                            ThemeMode.System -> "Follow System"
                            ThemeMode.Light -> "Light Theme"
                            ThemeMode.Dark -> "Dark Theme"
                        }
                    )
                },
                onClick = {
                    expanded = false
                    onModeChange(themeMode)
                },
                leadingIcon = {
                    Icon(
                        imageVector = when (themeMode) {
                            ThemeMode.System -> Icons.Filled.Contrast
                            ThemeMode.Light  -> Icons.Filled.LightMode
                            ThemeMode.Dark   -> Icons.Filled.DarkMode
                        },
                        contentDescription = null,
                        tint = if (mode == themeMode) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurface
                        }
                    )
                },
                trailingIcon = if (mode == themeMode) {
                    {
                        Icon(
                            imageVector = Icons.Filled.Check,
                            contentDescription = "Selected",
                            tint = MaterialTheme.colorScheme.primary
                        )
                    }
                } else null
            )
        }
    }
}