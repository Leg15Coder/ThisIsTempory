package com.motify.wrapper.ui.settings

import android.os.Bundle
import android.webkit.CookieManager
import android.webkit.WebStorage
import android.webkit.WebView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.motify.wrapper.R
import com.motify.wrapper.databinding.ActivitySettingsBinding

class SettingsActivity : AppCompatActivity() {
    private lateinit var binding: ActivitySettingsBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivitySettingsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.clearCacheButton.setOnClickListener {
            WebView(this).clearCache(true)
            AlertDialog.Builder(this)
                .setMessage(getString(R.string.ok))
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }

        binding.clearDataButton.setOnClickListener {
            CookieManager.getInstance().removeAllCookies(null)
            CookieManager.getInstance().flush()
            WebStorage.getInstance().deleteAllData()
            AlertDialog.Builder(this)
                .setMessage(getString(R.string.ok))
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }

        binding.checkUpdatesButton.setOnClickListener {
            AlertDialog.Builder(this)
                .setMessage("Проверка обновлений будет настроена после указания update URL")
                .setPositiveButton(android.R.string.ok, null)
                .show()
        }
    }
}

