package com.motify.wrapper.ui

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.google.firebase.auth.FirebaseAuth
import com.motify.wrapper.BuildConfig
import com.motify.wrapper.R
import com.motify.wrapper.auth.SessionSyncManager
import com.motify.wrapper.databinding.ActivityMainBinding
import com.motify.wrapper.links.DynamicLinkHandler
import com.motify.wrapper.network.NetworkUtils
import com.motify.wrapper.ui.settings.SettingsActivity
import com.motify.wrapper.updates.UpdateChecker
import com.motify.wrapper.util.AppUrls
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val sessionSyncManager by lazy { SessionSyncManager(this) }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupWebView()
        setupUi()
        syncSessionAndLoad(intent)

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (binding.webView.canGoBack()) binding.webView.goBack() else finish()
            }
        })
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(binding.webView, true)

        binding.webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadsImagesAutomatically = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
        }

        binding.webView.webChromeClient = WebChromeClient()
        binding.webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                val url = request?.url?.toString() ?: return false
                return if (url.startsWith("http://") || url.startsWith("https://")) {
                    false
                } else {
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                    true
                }
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                binding.pageLoader.visibility = View.GONE
                binding.errorView.root.visibility = View.GONE
                binding.swipeRefresh.isRefreshing = false
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: android.webkit.WebResourceError?
            ) {
                super.onReceivedError(view, request, error)
                if (request?.isForMainFrame == true) showErrorState()
            }
        }
    }

    private fun setupUi() {
        binding.swipeRefresh.setOnRefreshListener { binding.webView.reload() }
        binding.errorView.retryButton.setOnClickListener {
            binding.errorView.root.visibility = View.GONE
            binding.pageLoader.visibility = View.VISIBLE
            binding.webView.reload()
        }
    }

    private fun syncSessionAndLoad(intent: Intent?) {
        lifecycleScope.launch {
            if (!NetworkUtils.isConnected(this@MainActivity)) {
                showErrorState()
                return@launch
            }

            binding.pageLoader.visibility = View.VISIBLE

            if (FirebaseAuth.getInstance().currentUser != null) {
                sessionSyncManager.syncFirebaseSession()
            }

            val deepLink = DynamicLinkHandler.resolve(intent)
            binding.webView.loadUrl(deepLink?.toString() ?: AppUrls.home)
            launch { checkForUpdatesSilently() }
        }
    }

    private suspend fun checkForUpdatesSilently() {
        val info = withContext(Dispatchers.IO) { UpdateChecker().check() } ?: return
        val latest = info.latest_version ?: return
        if (latest != BuildConfig.VERSION_NAME && !info.store_url.isNullOrBlank()) {
            AlertDialog.Builder(this)
                .setTitle(getString(R.string.check_updates))
                .setMessage(info.update_message ?: "Доступна новая версия приложения: $latest")
                .setPositiveButton(R.string.open_update_link) { _, _ ->
                    startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(info.store_url)))
                }
                .setNegativeButton(R.string.cancel, null)
                .show()
        }
    }

    private fun showErrorState() {
        binding.pageLoader.visibility = View.GONE
        binding.swipeRefresh.isRefreshing = false
        binding.errorView.root.visibility = View.VISIBLE
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        lifecycleScope.launch {
            DynamicLinkHandler.resolve(intent)?.let { binding.webView.loadUrl(it.toString()) }
        }
    }

    override fun onCreateOptionsMenu(menu: Menu?): Boolean {
        menuInflater.inflate(R.menu.main_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == R.id.action_settings) {
            startActivity(Intent(this, SettingsActivity::class.java))
            return true
        }
        return super.onOptionsItemSelected(item)
    }
}
