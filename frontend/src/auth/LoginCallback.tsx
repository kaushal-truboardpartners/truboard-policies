import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader } from 'lucide-react'
import { userManager } from './authconfig'

export default function LoginCallback() {
  const navigate = useNavigate()
  const processed = useRef(false)

  useEffect(() => {
    if (processed.current) return
    processed.current = true

    userManager
      .signinRedirectCallback()
      .then(() => {
        navigate('/')
      })
      .catch((err) => {
        console.error('Login callback error:', err)
        navigate('/login')
      })
  }, [navigate])

  return (
    <div className="flex h-screen flex-col items-center justify-center space-y-4">
      <Loader className="h-10 w-10 animate-spin text-gray-500" />
      <p className="text-4xl font-bold">Processing login...</p>
    </div>
  )
}
