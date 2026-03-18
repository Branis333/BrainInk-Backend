try:
    from services.speech_services import SpeechService
    print('✅ SpeechService import successful')
    service = SpeechService()
    print('✅ SpeechService instantiation successful')
except Exception as e:
    print(f'❌ SpeechService error: {e}')

try:
    import whisper
    print('✅ Whisper import successful')
except Exception as e:
    print(f'❌ Whisper error: {e}')

try:
    import speech_recognition as sr
    print('✅ speech_recognition import successful')
except Exception as e:
    print(f'❌ speech_recognition error: {e}')
