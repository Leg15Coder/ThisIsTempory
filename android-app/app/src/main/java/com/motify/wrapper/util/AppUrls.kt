package com.motify.wrapper.util

import com.motify.wrapper.BuildConfig

object AppUrls {
    val base: String = BuildConfig.BASE_URL.trimEnd('/')
    val home: String = "$base/quest-app/"
    val logout: String = "$base/auth/logout"
}

