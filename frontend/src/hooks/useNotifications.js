import { useState, useEffect, useCallback } from 'react'
import api from '../api/client'

export function useNotifications() {
  const [notifications, setNotifications] = useState([])
  const [unreadCount, setUnreadCount] = useState(0)

  const fetch = useCallback(async () => {
    try {
      const { data } = await api.get('/notifications')
      setNotifications(data)
      setUnreadCount(data.filter((n) => !n.is_read).length)
    } catch {}
  }, [])

  const markRead = async (id) => {
    await api.patch(`/notifications/${id}/read`)
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, is_read: true } : n)))
    setUnreadCount((c) => Math.max(0, c - 1))
  }

  const markAllRead = async () => {
    const unread = notifications.filter((n) => !n.is_read)
    await Promise.all(unread.map((n) => api.patch(`/notifications/${n.id}/read`)))
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    setUnreadCount(0)
  }

  useEffect(() => {
    fetch()
    const timer = setInterval(fetch, 30000)
    return () => clearInterval(timer)
  }, [fetch])

  return { notifications, unreadCount, markRead, markAllRead, refresh: fetch }
}
