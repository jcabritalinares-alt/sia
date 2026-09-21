package com.sia.inventario

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.net.Uri
import android.net.http.SslError
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.text.InputType
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.Toast
import android.webkit.*
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.sia.inventario.databinding.ActivityMainBinding
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private var filePathCallback: ValueCallback<Array<Uri>>? = null
    private var cameraImageUri: Uri? = null

    private val PREFS_NAME = "SiaAppPrefs"
    private val KEY_SERVER_URL = "server_url"
    private val KEY_IS_CONFIGURED = "is_configured"
    private val KEY_MASTER_PASSWORD = "master_password"
    private val DEFAULT_URL = "http://192.168.1.100:8000"
    private val DEFAULT_MASTER_PASSWORD = "admin2026" // Clave maestra por defecto para administradores

    private val timeoutHandler = Handler(Looper.getMainLooper())
    private val CONNECTION_TIMEOUT_MS = 8000L // 8 segundos de timeout
    private var isPageLoadedSuccessfully = false

    private val timeoutRunnable = Runnable {
        if (!isPageLoadedSuccessfully) {
            binding.webView.stopLoading()
            binding.progressBar.visibility = View.GONE
            binding.swipeRefreshLayout.isRefreshing = false
            showOfflineScreen("Tiempo de espera agotado al conectar.")
        }
    }

    private val cameraPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        if (!isGranted) {
            Toast.makeText(this, "Permiso de cámara no concedido", Toast.LENGTH_SHORT).show()
        }
    }

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (filePathCallback == null) return@registerForActivityResult

        var results: Array<Uri>? = null
        if (result.resultCode == RESULT_OK) {
            val intentData = result.data
            if (intentData?.data != null) {
                results = arrayOf(intentData.data!!)
            } else if (cameraImageUri != null) {
                results = arrayOf(cameraImageUri!!)
            }
        }
        filePathCallback?.onReceiveValue(results)
        filePathCallback = null
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Verificar permisos de cámara
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
        }

        setupWebView()
        setupSwipeRefresh()
        setupBackButtonHandler()

        // Botón Reintentar en pantalla de error
        binding.btnRetry.setOnClickListener {
            loadServerUrl(getServerUrl())
        }

        // Botón de Cambiar URL en pantalla de error (Protegido con clave maestra)
        binding.btnChangeUrl.setOnClickListener {
            requestAdminAccess {
                showConfigServerDialog()
            }
        }

        // Botón flotante accesible en todo momento (Protegido con clave maestra)
        binding.fabSettings.setOnClickListener {
            requestAdminAccess {
                showConfigServerDialog()
            }
        }

        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val isConfigured = prefs.getBoolean(KEY_IS_CONFIGURED, false)
        val currentUrl = getServerUrl()

        // Si es la primera vez que se abre la app en el móvil o aún tiene la URL de emulador 10.0.2.2
        if (!isConfigured || currentUrl.contains("10.0.2.2")) {
            requestAdminAccess(isFirstSetup = true) {
                showConfigServerDialog(isFirstSetup = true)
            }
        } else {
            loadServerUrl(currentUrl)
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        val settings = binding.webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.allowFileAccess = true
        settings.allowContentAccess = true
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = true
        settings.setSupportZoom(true)
        settings.builtInZoomControls = true
        settings.displayZoomControls = false
        settings.mediaPlaybackRequiresUserGesture = false
        settings.cacheMode = WebSettings.LOAD_DEFAULT
        // Permitir contenido mixto y recursos HTTP dentro de HTTPS
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW

        binding.webView.webViewClient = object : WebViewClient() {
            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                isPageLoadedSuccessfully = false
                binding.progressBar.visibility = View.VISIBLE
                binding.layoutOffline.visibility = View.GONE

                // Iniciar temporizador de timeout
                timeoutHandler.removeCallbacks(timeoutRunnable)
                timeoutHandler.postDelayed(timeoutRunnable, CONNECTION_TIMEOUT_MS)
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                timeoutHandler.removeCallbacks(timeoutRunnable)
                isPageLoadedSuccessfully = true
                binding.progressBar.visibility = View.GONE
                binding.swipeRefreshLayout.isRefreshing = false
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                if (request?.isForMainFrame == true) {
                    timeoutHandler.removeCallbacks(timeoutRunnable)
                    isPageLoadedSuccessfully = false
                    val errorMsg = error?.description?.toString() ?: "Error de red"
                    showOfflineScreen("No se pudo conectar: $errorMsg")
                }
            }

            @SuppressLint("WebViewClientOnReceivedSslError")
            override fun onReceivedSslError(
                view: WebView?,
                handler: SslErrorHandler?,
                error: SslError?
            ) {
                // Permite conexiones seguras de túneles Cloudflare / locales sin pantalla en blanco
                handler?.proceed()
            }

            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val url = request?.url?.toString() ?: return false

                // Esquemas externos (teléfono, whatsapp, correo)
                if (url.startsWith("tel:") || url.startsWith("mailto:") || url.startsWith("whatsapp:") || url.startsWith("intent:")) {
                    try {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        startActivity(intent)
                        return true
                    } catch (e: Exception) {
                        Toast.makeText(this@MainActivity, "No hay aplicación para abrir este enlace", Toast.LENGTH_SHORT).show()
                        return true
                    }
                }

                // URLs web normales se cargan dentro del WebView
                return false
            }
        }

        binding.webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                binding.progressBar.progress = newProgress
                if (newProgress == 100) {
                    binding.progressBar.visibility = View.GONE
                }
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback?.onReceiveValue(null)
                this@MainActivity.filePathCallback = filePathCallback

                var takePictureIntent: Intent? = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
                if (takePictureIntent?.resolveActivity(packageManager) != null) {
                    var photoFile: File? = null
                    try {
                        photoFile = createImageFile()
                        takePictureIntent.putExtra("PhotoPath", photoFile.absolutePath)
                    } catch (ex: IOException) {
                        ex.printStackTrace()
                    }

                    if (photoFile != null) {
                        cameraImageUri = FileProvider.getUriForFile(
                            this@MainActivity,
                            "$packageName.fileprovider",
                            photoFile
                        )
                        takePictureIntent.putExtra(MediaStore.EXTRA_OUTPUT, cameraImageUri)
                    } else {
                        takePictureIntent = null
                    }
                }

                val contentSelectionIntent = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "image/*"
                }

                val intentArray: Array<Intent> = takePictureIntent?.let { arrayOf(it) } ?: emptyArray()

                val chooserIntent = Intent(Intent.ACTION_CHOOSER).apply {
                    putExtra(Intent.EXTRA_INTENT, contentSelectionIntent)
                    putExtra(Intent.EXTRA_TITLE, "Seleccionar o Tomar Foto")
                    putExtra(Intent.EXTRA_INITIAL_INTENTS, intentArray)
                }

                fileChooserLauncher.launch(chooserIntent)
                return true
            }
        }
    }

    private fun loadServerUrl(url: String) {
        val cleanUrl = sanitizeUrl(url)
        binding.layoutOffline.visibility = View.GONE
        binding.progressBar.visibility = View.VISIBLE
        binding.tvErrorUrl.text = "Conectando a: $cleanUrl"
        binding.webView.loadUrl(cleanUrl)
    }

    private fun showOfflineScreen(reason: String) {
        val currentUrl = getServerUrl()
        binding.layoutOffline.visibility = View.VISIBLE
        binding.progressBar.visibility = View.GONE
        binding.tvErrorTitle.text = "Sin Conexión al Servidor SIA"
        binding.tvErrorUrl.text = "Servidor configurado: $currentUrl\n($reason)"
    }

    private fun setupSwipeRefresh() {
        binding.swipeRefreshLayout.setOnRefreshListener {
            loadServerUrl(getServerUrl())
        }
        binding.swipeRefreshLayout.setColorSchemeResources(
            R.color.primary,
            R.color.primary_dark
        )
    }

    private fun setupBackButtonHandler() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.webView.canGoBack()) {
                    binding.webView.goBack()
                } else {
                    finish()
                }
            }
        })
    }

    @Throws(IOException::class)
    private fun createImageFile(): File {
        val timeStamp: String = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
        val storageDir: File? = getExternalFilesDir(Environment.DIRECTORY_PICTURES)
        return File.createTempFile("JPEG_${timeStamp}_", ".jpg", storageDir)
    }

    private fun getServerUrl(): String {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_SERVER_URL, DEFAULT_URL) ?: DEFAULT_URL
    }

    private fun sanitizeUrl(url: String): String {
        var cleanUrl = url.trim()
        if (!cleanUrl.startsWith("http://") && !cleanUrl.startsWith("https://")) {
            cleanUrl = "http://$cleanUrl"
        }
        return cleanUrl
    }

    private fun saveAndApplyServerUrl(url: String) {
        val cleanUrl = sanitizeUrl(url)
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(KEY_SERVER_URL, cleanUrl)
            .putBoolean(KEY_IS_CONFIGURED, true)
            .apply()

        Toast.makeText(this, "Conectando a: $cleanUrl", Toast.LENGTH_SHORT).show()
        loadServerUrl(cleanUrl)
    }

    private fun getMasterPassword(): String {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_MASTER_PASSWORD, DEFAULT_MASTER_PASSWORD) ?: DEFAULT_MASTER_PASSWORD
    }

    private fun requestAdminAccess(isFirstSetup: Boolean = false, onSuccess: () -> Unit) {
        val container = FrameLayout(this)
        val params = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.WRAP_CONTENT
        )
        val margin = (20 * resources.displayMetrics.density).toInt()
        params.setMargins(margin, 8, margin, 8)

        val inputPassword = EditText(this)
        inputPassword.layoutParams = params
        inputPassword.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        inputPassword.hint = "Clave de Administrador"
        container.addView(inputPassword)

        AlertDialog.Builder(this)
            .setTitle("🔒 Clave Maestra Requerida")
            .setMessage("Solo el administrador del sistema puede cambiar la dirección del servidor.")
            .setView(container)
            .setPositiveButton("Verificar") { dialog, _ ->
                val enteredPass = inputPassword.text.toString()
                if (enteredPass == getMasterPassword()) {
                    dialog.dismiss()
                    onSuccess()
                } else {
                    Toast.makeText(
                        this,
                        "❌ Clave maestra incorrecta. Acceso restringido.",
                        Toast.LENGTH_LONG
                    ).show()
                    if (isFirstSetup) {
                        loadServerUrl(getServerUrl())
                    }
                    dialog.dismiss()
                }
            }
            .setNegativeButton("Cancelar") { dialog, _ ->
                if (isFirstSetup) {
                    loadServerUrl(getServerUrl())
                }
                dialog.cancel()
            }
            .setCancelable(!isFirstSetup)
            .show()
    }

    private fun showConfigServerDialog(isFirstSetup: Boolean = false) {
        val container = FrameLayout(this)
        val params = FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.WRAP_CONTENT
        )
        val margin = (20 * resources.displayMetrics.density).toInt()
        params.setMargins(margin, 8, margin, 8)

        val input = EditText(this)
        input.layoutParams = params
        input.hint = "Ej: http://192.168.1.50:8000 o https://xxx.trycloudflare.com"
        
        val currentUrl = getServerUrl()
        // Si tiene la URL del emulador 10.0.2.2, limpiamos el campo para facilitar escribir la real
        if (currentUrl.contains("10.0.2.2")) {
            input.setText("http://192.168.1.")
        } else {
            input.setText(currentUrl)
        }
        input.setSelection(input.text.length)
        container.addView(input)

        val dialogTitle = if (isFirstSetup) "⚙️ Configurar Servidor SIA" else getString(R.string.title_config_server)
        val dialogMsg = if (isFirstSetup) {
            "Ingrese la dirección IP de su PC (ej. http://192.168.1.15:8000) o la URL de Cloudflare:"
        } else {
            getString(R.string.msg_enter_url)
        }

        AlertDialog.Builder(this)
            .setTitle(dialogTitle)
            .setMessage(dialogMsg)
            .setView(container)
            .setPositiveButton(R.string.btn_save) { dialog, _ ->
                val newUrl = input.text.toString()
                if (newUrl.isNotBlank()) {
                    saveAndApplyServerUrl(newUrl)
                }
                dialog.dismiss()
            }
            .setNegativeButton(if (isFirstSetup) "Usar por defecto" else getString(R.string.btn_cancel)) { dialog, _ ->
                if (isFirstSetup) {
                    loadServerUrl(getServerUrl())
                }
                dialog.cancel()
            }
            .setCancelable(!isFirstSetup)
            .show()
    }

    override fun onDestroy() {
        timeoutHandler.removeCallbacksAndMessages(null)
        super.onDestroy()
    }

    override fun onCreateOptionsMenu(menu: Menu?): Boolean {
        menu?.add(0, 1, 0, "Configurar URL de Servidor")
            ?.setIcon(android.R.drawable.ic_menu_preferences)
            ?.setShowAsAction(MenuItem.SHOW_AS_ACTION_NEVER)
        return super.onCreateOptionsMenu(menu)
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        return when (item.itemId) {
            1 -> {
                requestAdminAccess {
                    showConfigServerDialog()
                }
                true
            }
            else -> super.onOptionsItemSelected(item)
        }
    }
}

